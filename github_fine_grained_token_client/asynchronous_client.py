"""
`async`/`await`-based GitHub token client
"""
import asyncio
from collections.abc import Mapping
from contextlib import AbstractContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from logging import Logger, getLogger
from pathlib import Path
from typing import AsyncIterator, Sequence, Type, TypeVar, cast

import aiohttp
import dateparser
from bs4 import BeautifulSoup, Tag

from github_fine_grained_token_client.two_factor_authentication import (
    TwoFactorOtpProvider,
)

from .abstract_http_session import AbstractHttpSession
from .common import (
    EXPIRED,
    AllRepositories,
    Expired,
    FineGrainedTokenBulkInfo,
    FineGrainedTokenCompletePersistentInfo,
    FineGrainedTokenIndividualInfo,
    FineGrainedTokenScope,
    FineGrainedTokenStandardInfo,
    LoginError,
    NotImplementedTwoFactorAuthenticationMethodError,
    PublicRepositories,
    RepositoryNotFoundError,
    SelectRepositories,
    TokenCreationError,
    TokenNameAlreadyTakenError,
    TwoFactorAuthenticationError,
    UnexpectedContentError,
    UnexpectedPageError,
)
from .credentials import GithubCredentials
from .dev import PossiblePermission, PossiblePermissions
from .permissions import (
    ALL_PERMISSION_KEYS,
    AnyPermissionKey,
    PermissionValue,
    permission_from_str,
)
from .persisting_http_session import PersistingHttpClientSession
from .utils.bs4 import expect_single_str, expect_single_str_or_none
from .utils.sequences import exactly_one, one_or_none

default_logger = getLogger(__name__)


@dataclass
class _FineGrainedTokenBulkInternalInfo(FineGrainedTokenBulkInfo):
    """
    Internally useful information on a fine-grained token from one request.
    """

    deletion_authenticity_token: str


@asynccontextmanager
async def async_client(
    credentials: GithubCredentials,
    two_factor_otp_provider: TwoFactorOtpProvider,
    persist_to: Path | None = None,
    base_url: str = "https://github.com",
    logger: Logger = default_logger,
) -> AsyncIterator["AsyncClientSession"]:
    """
    Context manager for launching an async client session.

    This is the main starting point for using the async client.

    Args:
        credentials: Credentials to log into GitHub with.
        two_factor_otp_provider: Provider of one-time passwords for
            two-factor authentication.
        persist_to: Directory in which to persist the session state (currently
            just cookies). Will also be used to load previously persisted
            sessions. ``None`` means no persistence.
        base_url: GitHub base URL.
        logger: Logger to log messages to.

    Returns:
      A context manager for the async session.
    """
    async with aiohttp.ClientSession(raise_for_status=True) as http_session:
        with AsyncClientSession.make_with_cookies_loaded(
            http_session,
            credentials,
            two_factor_otp_provider,
            persist_to,
            base_url,
            logger,
        ) as session:
            yield session


T = TypeVar("T", bound="AsyncClientSession")


class AsyncClientSession(AbstractContextManager):
    """
    Async token client session.

    Should not be instantiated directly but only through :any:`async_client`.

    A session's lifecycle corresponds to that of the HTTP client which is used
    to perform operations on the GitHub web interface. When multiple operations
    have to be performed in sequence, it makes sense to do so in the a single
    session to minimize the number of times the connection has to be
    re-established.
    """

    def __init__(
        self,
        http_session: aiohttp.ClientSession,
        credentials: GithubCredentials,
        two_factor_otp_provider: TwoFactorOtpProvider,
        persist_to: Path | None = None,
        base_url: str = "https://github.com",
        logger: Logger = default_logger,
    ):
        # XXX cast required because Mypy doesn't support ABC registration...
        # https://github.com/python/mypy/issues/2922
        http_session_: AbstractHttpSession = cast(
            AbstractHttpSession, http_session
        )
        self.inner_http_session = http_session_
        if persist_to is not None:
            http_session_ = PersistingHttpClientSession(
                http_session_, persist_to
            )
        self.http_session = http_session_
        self.credentials = credentials
        self.two_factor_otp_provider = two_factor_otp_provider
        self.base_url = base_url
        self.logger = logger

    @property
    def _persisting_http_session(self) -> PersistingHttpClientSession | None:
        """
        The persisting HTTP session, if any.
        """
        if isinstance(self.http_session, PersistingHttpClientSession):
            return self.http_session
        return None

    @classmethod
    def make_with_cookies_loaded(cls: Type[T], *args, **kwargs) -> T:
        """
        Convenience method to instantiate with cookies already loaded.
        """
        obj = cls(*args, **kwargs)
        obj.load_cookies(suppress_errors=True)
        return obj

    def load_cookies(self, suppress_errors: bool = False):
        """
        Load cookies from persistence location (if any) into HTTP session.
        """
        if self._persisting_http_session is not None:
            self._persisting_http_session.load(suppress_errors)

    def __exit__(self, *args, **kwargs) -> None:
        if self._persisting_http_session is not None:
            self._persisting_http_session.__exit__(*args, **kwargs)

    async def _get_parsed_response_html(
        self, response: aiohttp.ClientResponse
    ) -> BeautifulSoup:
        response_text = await response.text()
        return BeautifulSoup(response_text, "html.parser")

    def _get_authenticity_token(
        self, html: BeautifulSoup | Tag, form_id: str | None = None
    ) -> str:
        selection_str = 'input[name="authenticity_token"]'
        if form_id:
            selection_str = f'form[id="{form_id}"] ' + selection_str
        authenticity_token = expect_single_str_or_none(
            (
                one_or_none(html.select(selection_str))
                or cast(dict[str, str], {})
            ).get("value")
        )
        if authenticity_token is None:
            raise UnexpectedContentError("no authenticity token found on page")
        return authenticity_token

    def _get_hidden_form_inputs(
        self, html: BeautifulSoup | Tag
    ) -> Mapping[str, str]:
        return {
            expect_single_str(input_elem["name"]): expect_single_str(
                input_elem["value"]
            )
            for input_elem in html.select('form input[type="hidden"]')
            if "value" in input_elem.attrs
        }

    def _make_url(self, path: str) -> str:
        return self.base_url.rstrip("/") + path

    @asynccontextmanager
    async def _handle_login(
        self, response: aiohttp.ClientResponse
    ) -> AsyncIterator[tuple[bool, aiohttp.ClientResponse]]:
        """
        Handle login intercept.

        To be used as a context manager.

        Args:
            response: Response which may or may not contain an intercept. Will
                be closed if there was one.

        Returns:
            A tuple of a boolean and a response. The boolean will be `True` if
            a login was actually performed, `False` if nothing was done. The
            response will be the new response after logging in or the old one
            if nothing was done.
        """
        if not str(response.url).startswith(self._make_url("/login")):
            self.logger.info("no login required")
            yield (False, response)
        else:
            self.logger.info("login required")
            destination_url = response.url.query.get("return_to")
            html = await self._get_parsed_response_html(response)
            hidden_inputs = self._get_hidden_form_inputs(html)
            response.release()  # free up connection for next request
            async with self.http_session.post(
                self._make_url("/session"),
                data={
                    "login": self.credentials.username,
                    "password": self.credentials.password,
                    **hidden_inputs,
                },
            ) as response:
                if str(response.url) == self._make_url("/session"):
                    html = await self._get_parsed_response_html(response)
                    login_error = one_or_none(
                        html.select("#js-flash-container")
                    )
                    if login_error is not None:
                        raise LoginError(login_error.get_text().strip())
                    raise UnexpectedContentError(
                        "ended up back on login page but not sure why"
                    )
                if str(response.url).startswith(
                    self._make_url("/sessions/two-factor/")
                ) and str(response.url) != self._make_url(
                    "/sessions/two-factor/app"
                ):
                    raise NotImplementedTwoFactorAuthenticationMethodError(
                        f"ended up on page {response.url} which indicates "
                        "that your default 2FA method is something other than "
                        '"authenticator app", but currently, only 2FA via an '
                        "authenticator app is supported and must be set as "
                        "the default in your GitHub authentication settings; "
                        "issue: https://gitlab.com/smheidrich/"
                        "github-fine-grained-token-client/-/issues/14"
                    )
                if (
                    destination_url is not None
                    and str(response.url) != destination_url
                    and str(response.url)
                    != self._make_url("/sessions/two-factor/app")
                ):
                    raise UnexpectedPageError(
                        f"ended up on unexpected page {response.url} after "
                        f"login (expected {destination_url})"
                    )
                yield (True, response)

    @asynccontextmanager
    async def _confirm_password(
        self, response: aiohttp.ClientResponse
    ) -> AsyncIterator[aiohttp.ClientResponse]:
        """
        Handle password confirmation intercept.

        To be used as a context manager.

        Args:
            response: Response which may or may not contain an intercept. Will
                be closed if there was one.

        Returns:
            A response which will be the new response after confirming the
            password or the old one if nothing was done.
        """
        html = await self._get_parsed_response_html(response)
        confirm_access_heading = one_or_none(html.select("#sudo > div > h1"))
        if confirm_access_heading is None:
            self.logger.info("no password confirmation required")
            yield response
        else:
            self.logger.info("password confirmation required")
            hidden_inputs = self._get_hidden_form_inputs(html)
            form_elems = html.select("form")
            if not form_elems:
                raise UnexpectedContentError("no form found on page")
            elif len(form_elems) == 1:
                # password confirmation dialog for users without 2FA enabled
                form = exactly_one(form_elems)
            else:
                # password confirmation dialog for users with 2FA (OTP) enabled
                # (has 3 forms, 1 for confirm via OTP, 2 for via password...)
                form = exactly_one(html.select("noscript form"))
            response.release()  # free up connection for next request
            async with self.http_session.post(
                (
                    form_action
                    if any(
                        (
                            form_action := expect_single_str(form["action"])
                        ).startswith(scheme)
                        for scheme in ["https://", "http://"]
                    )
                    else self._make_url(form_action)
                ),
                data={
                    "sudo_password": self.credentials.password,
                    **hidden_inputs,
                },
                headers={"Referer": str(response.url)},
            ) as response:
                if str(response.url).startswith(
                    self.base_url.rstrip("/") + "/sessions/sudo"
                ):
                    html = await self._get_parsed_response_html(response)
                    login_error = one_or_none(
                        html.select("#js-flash-container")
                    )
                    if login_error is not None:
                        raise LoginError(login_error.get_text().strip())
                    raise UnexpectedContentError(
                        "ended up back on login page but not sure why"
                    )
                yield response

    @asynccontextmanager
    async def _handle_two_factor_auth(
        self, response: aiohttp.ClientResponse
    ) -> AsyncIterator[aiohttp.ClientResponse]:
        # TODO implement 2FA methods other than OTP
        if not str(response.url).startswith(
            self._make_url("/sessions/two-factor/app")
        ):
            self.logger.info("no two-factor authentication required")
            yield response
        else:
            self.logger.info("two-factor authentication required")
            html = await self._get_parsed_response_html(response)
            hidden_inputs = self._get_hidden_form_inputs(html)
            otp = await self.two_factor_otp_provider.get_otp_for_user(
                self.credentials.username
            )
            response.release()  # free up connection for next request
            async with self._post(
                "/sessions/two-factor",
                data={
                    "app_otp": otp,
                    **hidden_inputs,
                },
            ) as response:
                if str(response.url).startswith(
                    self._make_url("/sessions/two-factor")
                ):
                    html = await self._get_parsed_response_html(response)
                    error_elem = one_or_none(
                        html.select("#js-flash-container")
                    )
                    if error_elem is not None:
                        raise TwoFactorAuthenticationError(
                            error_elem.get_text().strip()
                        )
                    raise UnexpectedContentError(
                        "ended up back on two-factor authentication page "
                        "but not sure why"
                    )
                yield response

    @asynccontextmanager
    async def _handle_auth(
        self, response: aiohttp.ClientResponse
    ) -> AsyncIterator[aiohttp.ClientResponse]:
        """
        Handle auth-related intercepts (login & confirm password).

        To be used as a context manager.

        Args:
            response: Response which may or may not contain an intercept. Will
                be closed if there was one.

        Returns:
            A response which will be the new response after confirming the
            password or the old one if nothing was done.
        """
        async with self._handle_login(response) as (
            _,
            response,
        ), self._handle_two_factor_auth(
            response
        ) as response, self._confirm_password(
            response
        ) as response:
            yield response

    def _get(
        self, path: str, **kwargs
    ) -> aiohttp.client._RequestContextManager:
        return self.http_session.get(self._make_url(path), **kwargs)

    def _post(
        self, path: str, **kwargs
    ) -> aiohttp.client._RequestContextManager:
        return self.http_session.post(self._make_url(path), **kwargs)

    @asynccontextmanager
    async def _auth_handling_get(
        self, path, **kwargs
    ) -> AsyncIterator[aiohttp.ClientResponse]:
        async with self._get(path, **kwargs) as response, self._handle_auth(
            response
        ) as response:
            yield response

    @asynccontextmanager
    async def _auth_handling_post(
        self, path, **kwargs
    ) -> AsyncIterator[aiohttp.ClientResponse]:
        async with self._post(path, **kwargs) as response, self._handle_auth(
            response
        ) as response:
            yield response

    async def _get_repository_id(
        self, target_name: str, repository_name: str
    ) -> int:
        async with self._get(
            "/settings/personal-access-tokens/suggestions",
            params={"target_name": target_name, "q": repository_name},
        ) as response:
            html = await self._get_parsed_response_html(response)
        for button_elem in html.select("button"):
            input_elem = one_or_none(button_elem.select("input"))
            assert input_elem is not None
            name_elem = one_or_none(
                button_elem.select(".select-menu-item-text")
            )
            if name_elem is None:
                continue
            name = name_elem.contents[1].get_text()[1:]
            if name == repository_name:
                return int(expect_single_str(input_elem["value"]))
        raise RepositoryNotFoundError(
            f"no such repository: {target_name}/{repository_name}"
        )

    async def create_token(
        self,
        name: str,
        expires: date | timedelta,
        description: str = "",
        resource_owner: str | None = None,
        scope: FineGrainedTokenScope = PublicRepositories(),
        permissions: Mapping[AnyPermissionKey, PermissionValue] | None = None,
    ) -> str:
        """
        Create a new fine-grained token on GitHub.

        Args:
            name: Name of the token to create.
            expires: Expiration date of the token to create. GitHub currently
                only allows expiration dates up to 1 year in the future.
            description: Description of the token to create.
            resource_owner: Owner of the token to create. Defaults to username
                used to log in.
            scope: The token's desired scope.
            permissions: Permissions the token should have, as a mapping from
                permissions to the desired value (read or write = read+write).

        Returns:
            The created token.
        """
        # normalize and validate args
        expires_date = (
            date.today() + expires
            if isinstance(expires, timedelta)
            else expires
        )
        if permissions is None:
            permissions = {}
        if resource_owner is None:
            resource_owner = self.credentials.username
        # /normalize and validate args
        async with self._auth_handling_get(
            "/settings/personal-access-tokens/new"
        ) as response:
            html = await self._get_parsed_response_html(response)
        # get dynamic form data
        authenticity_token = self._get_authenticity_token(
            html, form_id="new_user_programmatic_access"
        )
        # build form data & submit
        repository_ids: list[int]
        if isinstance(scope, PublicRepositories):
            install_target = "none"
            repository_ids = []
        elif isinstance(scope, AllRepositories):
            install_target = "all"
            repository_ids = []
        elif isinstance(scope, SelectRepositories):
            install_target = "selected"
            # fetch repo IDs given names
            repository_ids = [
                await self._get_repository_id(resource_owner, repository_name)
                for repository_name in scope.names
            ]
        else:
            raise ValueError(f"invalid scope {scope}")
        async with self._auth_handling_post(
            "/settings/personal-access-tokens",
            data={
                "authenticity_token": authenticity_token,
                "user_programmatic_access[name]": name,
                "user_programmatic_access[default_expires_at]": "custom",
                "user_programmatic_access[custom_expires_at]": (
                    expires_date.strftime("%Y-%m-%d")
                ),
                "user_programmatic_access[description]": description,
                "target_name": resource_owner,
                "install_target": install_target,
                "repository_ids[]": repository_ids,
                **{
                    "integration[default_permissions]"
                    f"[{permission_key.value}]": (
                        permissions.get(
                            permission_key, PermissionValue.NONE
                        ).value
                    )
                    for permission_key in ALL_PERMISSION_KEYS
                },
            },
        ) as response:
            # ^ confirm password again if necessary (rare but can happen)
            # TODO unsure if we have to re-send the form data in this case...
            #
            html = await self._get_parsed_response_html(response)
        # get value of newly created token
        token_elem = one_or_none(html.select("#new-access-token"))
        if token_elem is None:
            error_elem = one_or_none(
                html.select(".error,.flash-error.flash-full")
            )
            if error_elem:
                error = error_elem.get_text().strip()
                if "name has already been taken" in error.lower():
                    raise TokenNameAlreadyTakenError(error.lower())
                raise TokenCreationError(f"error creating token: {error}")
            raise UnexpectedContentError("no token value found on page")
        token_value = expect_single_str(token_elem["value"])
        return token_value

    async def login(self) -> bool:
        """
        Log into GitHub if necessary.

        Normally, this does not need to be called explicitly as all other
        methods in this class perform logins automatically.

        One use case for this is to find out whether the given credentials are
        correct without doing anything else. It should however be noted that an
        actual login will only be performed when necessary, i.e. when the
        session's current state (resulting from loaded session state or prior
        actions) isn't already logged in.

        Returns:
            ``True`` if a login was actually performed, ``False`` if nothing
            was done.
        """
        async with self._get("/login") as response, self._handle_login(
            response
        ) as (did_login, response), self._handle_two_factor_auth(
            response
        ) as response:
            pass
        return did_login

    async def get_tokens_bulk(self) -> Sequence[FineGrainedTokenBulkInfo]:
        """
        Get fine-grained token list and some information via a single request.

        Note that the returned information does not include the expiration
        date, which would require additional HTTP requests to fetch. To
        retrieve tokens and their expiration dates, you can use
        :py:meth:`~AsyncClientSession.get_tokens` instead.

        Returns:
            List of tokens.
        """
        return [
            FineGrainedTokenBulkInfo(
                id=info.id, name=info.name, last_used_str=info.last_used_str
            )
            for info in await self._get_tokens_bulk_internal()
        ]

    async def _get_tokens_bulk_internal(
        self,
    ) -> Sequence[_FineGrainedTokenBulkInternalInfo]:
        async with self._auth_handling_get(
            "/settings/tokens?type=beta"
        ) as response:
            html = await self._get_parsed_response_html(response)
        listgroup_elem = one_or_none(html.select(".listgroup"))
        if not listgroup_elem:
            raise UnexpectedContentError("no token list found on page")
        token_elems = html.select(
            ".listgroup > .access-token > .listgroup-item"
        )
        token_list = []
        for token_elem in token_elems:
            last_used_str = (
                exactly_one(token_elem.select(".last-used")).get_text().strip()
            )
            details_link = exactly_one(
                token_elem.select(".token-description > strong a")
            )
            id_ = int(expect_single_str(details_link["href"]).split("/")[-1])
            name = details_link.get_text().strip()
            deletion_authenticity_token = self._get_authenticity_token(
                token_elem
            )
            entry = _FineGrainedTokenBulkInternalInfo(
                id=id_,
                name=name,
                last_used_str=last_used_str,
                deletion_authenticity_token=deletion_authenticity_token,
            )
            token_list.append(entry)
        return token_list

    async def get_token_expiration(self, token_id: int) -> datetime | Expired:
        """
        Retrieve the expiration date of a single fine-grained token.

        Args:
            token_id: The fine-grained token's ID.

        Returns:
            The fine-grained token's expiration date.
        """
        async with self._get(
            f"/settings/personal-access-tokens/{token_id}/expiration?page=1"
        ) as response:
            html = await self._get_parsed_response_html(response)
            expires_str = html.get_text().strip()
            if any(
                expires_str.lower().startswith(x)
                for x in ("expires on ", "expired on ")
            ):
                expires_str = expires_str[len("expire* on ") :]
            expires = dateparser.parse(expires_str)
            if expires is None:
                if "expired" in expires_str:
                    return EXPIRED
                raise UnexpectedContentError(
                    f"could not parse expiration date {expires_str}"
                )
        return expires

    async def get_tokens(
        self,
    ) -> Sequence[FineGrainedTokenStandardInfo]:
        """
        Get list of fine-grained tokens with all data shown on the tokens page.

        This has to make one additional HTTP request for each token to get its
        expiration date (this is also how it works on GitHub's fine-grained
        tokens page), so it will be a bit slower than
        :py:meth:`~AsyncClientSession.get_tokens_bulk`.

        Returns:
            List of tokens.
        """
        summaries = await self.get_tokens_bulk()
        fetch_expiration_tasks = [
            asyncio.create_task(self.get_token_expiration(summary.id))
            for summary in summaries
        ]
        expiration_dates = await asyncio.gather(*fetch_expiration_tasks)
        return [
            FineGrainedTokenStandardInfo(
                id=summary.id,
                name=summary.name,
                last_used_str=summary.last_used_str,
                expires=expiration_date,
            )
            for summary, expiration_date in zip(summaries, expiration_dates)
        ]

    async def get_token_info_by_id(
        self, token_id: int
    ) -> FineGrainedTokenIndividualInfo:
        """
        Get information on a token (by ID) as shown on the token's own page.

        Args:
            token_id: ID of the token. Can be obtained by calling
                ``get_tokens`` and iterating over the results.

        Returns:
            Token information.
        """
        async with self._auth_handling_get(
            f"/settings/personal-access-tokens/{token_id}"
        ) as response:
            html = await self._get_parsed_response_html(response)
        # parse name
        name = exactly_one(html.select("h2 > p")).get_text().strip()
        # parse creation date
        creation_date_elem = exactly_one(
            html.select("div.clearfix.mb-1 p.float-left")
        )
        creation_date_full_str = creation_date_elem.get_text().strip()
        # Can either say "Created on DATE" or "Created today", but dateparser
        # ignores the "on" automatically so we can leave it in
        assert creation_date_full_str.startswith("Created ")
        creation_date_str = creation_date_full_str[len("Created ") :]
        creation_date = dateparser.parse(creation_date_str)
        if creation_date is None:
            raise UnexpectedContentError(
                f"could not parse creation date {creation_date_str}"
            )
        # parse permissions
        permissions = self._parse_token_permissions(html)
        # get expiration date
        expiration_date = await self.get_token_expiration(token_id)
        return FineGrainedTokenIndividualInfo(
            id=token_id,
            name=name,
            expires=expiration_date,
            created=creation_date,
            permissions=permissions,
        )

    async def get_token_info_by_name(
        self, name: str
    ) -> FineGrainedTokenIndividualInfo:
        """
        Get information on a token (by name) as shown on the token's own page.

        Like :any:`AsyncClientSession.get_token_info_by_id` but by name instead
        of by ID. Needs to make one more request than that one.

        Args:
            name: Name of the token.

        Returns:
            Token information.
        """
        info_by_name = {
            info.name: info for info in await self.get_tokens_bulk()
        }
        if name not in info_by_name:
            raise KeyError(f"no token named {name!r}")
        info = info_by_name[name]
        return await self.get_token_info_by_id(info.id)

    async def get_complete_persistent_token_info_by_id(
        self, token_id: int
    ) -> FineGrainedTokenIndividualInfo:
        """
        Get all persistent information on a token (by ID).

        This queries not only the token's own page but also the list of tokens
        where the last-used information resides.

        Args:
            token_id: ID of the token. Can be obtained by calling
                ``get_tokens`` and iterating over the results.

        Returns:
            Token information.
        """
        bulk_tokens_info = await self.get_tokens_bulk()
        bulk_token_info = exactly_one(
            [t for t in bulk_tokens_info if t.id == token_id]
        )
        individual_token_info = await self.get_token_info_by_id(token_id)
        return FineGrainedTokenCompletePersistentInfo(
            id=token_id,
            name=individual_token_info.name,
            expires=individual_token_info.expires,
            created=individual_token_info.created,
            permissions=individual_token_info.permissions,
            last_used_str=bulk_token_info.last_used_str,
        )

    async def get_complete_persistent_token_info_by_name(
        self, name: str
    ) -> FineGrainedTokenIndividualInfo:
        """
        Get all persistent information on a token (by name).

        Like
        :py:meth:`~AsyncClientSession.get_complete_persistent_token_info_by_id`
        but by name instead of by ID. Uses the same amount of requests though.

        Args:
            name: Name of the token.

        Returns:
            Token information.
        """
        bulk_info_by_name = {
            bulk_info.name: bulk_info
            for bulk_info in await self.get_tokens_bulk()
        }
        if name not in bulk_info_by_name:
            raise KeyError(f"no token named {name!r}")
        bulk_info = bulk_info_by_name[name]
        token_id = bulk_info.id
        individual_info = await self.get_token_info_by_id(token_id)
        return FineGrainedTokenCompletePersistentInfo(
            id=token_id,
            name=individual_info.name,
            expires=individual_info.expires,
            created=individual_info.created,
            permissions=individual_info.permissions,
            last_used_str=bulk_info.last_used_str,
        )

    def _parse_token_permissions(
        self, html
    ) -> dict[AnyPermissionKey, PermissionValue]:
        """
        Parse a token's permissions from its own page.
        """
        permissions_dict = {}
        permission_elems = html.select('li input[type="radio"]:checked')
        for permission_elem in permission_elems:
            full_identifier = permission_elem["name"]
            identifier = full_identifier.split("[")[-1].strip("]")  # TODO refa
            try:
                key = permission_from_str(identifier)
            except KeyError:
                self.logger.warn(
                    f"unknown permission {identifier!r} - skipping; "
                    "consider upgrading your github-fine-grained-token-client "
                    "version and filing an issue if the warning persists"
                )
                continue
            value = PermissionValue(permission_elem["value"])
            permissions_dict[key] = value
        if not permissions_dict:
            raise UnexpectedContentError(
                "no permission inputs found for token"
            )
        return permissions_dict

    async def delete_token_by_id(self, id: int) -> None:
        """
        Delete fine-grained token identified by its ID from GitHub.

        Contrary to what you might think, this isn't any faster than
        :py:meth:`~AsyncClientSession.delete_token_by_name` as both need to
        make one extra request to fetch an authenticity token.

        Args:
            id: ID of the token to delete.
        """
        # get list first because each has its own deletion authenticity token
        info_by_id = {
            info.id: info for info in await self._get_tokens_bulk_internal()
        }
        if id not in info_by_id:
            raise KeyError(f"no token with ID {id!r}")
        # delete
        await self._delete_token_by_internal_info(info_by_id[id])

    async def delete_token_by_name(self, name: str) -> None:
        """
        Delete fine-grained token identified by its name from GitHub.

        Args:
            name: Name of the token to delete.
        """
        # get list first because each has its own deletion authenticity token
        info_by_name = {
            info.name: info for info in await self._get_tokens_bulk_internal()
        }
        if name not in info_by_name:
            raise KeyError(f"no token named {name!r}")
        # delete
        await self._delete_token_by_internal_info(info_by_name[name])

    async def _delete_token_by_internal_info(
        self, info: _FineGrainedTokenBulkInternalInfo
    ) -> None:
        self.logger.info(f"deleting token {info.name!r}")
        async with self._auth_handling_post(
            f"/settings/personal-access-tokens/{info.id}",
            data={
                "_method": "delete",
                "authenticity_token": (info.deletion_authenticity_token),
            },
            headers={
                "Referer": (
                    self.base_url.rstrip("/") + "/settings/tokens?type=beta"
                )
            },
        ) as response:
            html = await self._get_parsed_response_html(response)
        alert = html.select_one('div[role="alert"]')
        if alert is None:
            raise UnexpectedContentError("deletion result not found on page")
        alert_text = alert.get_text().strip()
        if not alert_text == "Deleted personal access token":
            raise UnexpectedContentError(f"deletion failed: {alert_text!r}")
        self.logger.info(f"deleted token {info.name!r}")

    async def get_possible_permissions(self) -> PossiblePermissions:
        """
        Retrieve list of possible permissions one can use for tokens.

        This is only useful for the development of this library and there isn't
        much of a point in you using it. Users of this library can access all
        possible permissions by iterating over the :any:`RepositoryPermission`
        and :any:`AccountPermission` enums instead, which has the advantage of
        being a fully local operation.
        """
        async with self._auth_handling_get(
            "/settings/personal-access-tokens/new"
        ) as response:
            html = await self._get_parsed_response_html(response)
        possible_permissions_dict: dict[str, list] = {}
        for permission_group in ["repository", "user"]:
            possible_permissions_dict[permission_group] = []
            permission_elems = html.select(
                f'*[aria-label="{permission_group}-permissions"] li'
            )
            for permission_elem in permission_elems:
                name = exactly_one(
                    permission_elem.select("div > div > strong")
                ).get_text()
                description = (
                    exactly_one(permission_elem.select("div.text-small"))
                    .get_text()
                    .strip()
                )
                input_elems = permission_elem.select("input")
                full_identifier = expect_single_str(input_elems[0]["name"])
                allowed_values = tuple(
                    PermissionValue(expect_single_str(input_elem["value"]))
                    for input_elem in input_elems
                )
                identifier = full_identifier.split("[")[-1].strip("]")
                possible_permission = PossiblePermission(
                    identifier, name, description, allowed_values
                )
                possible_permissions_dict[permission_group].append(
                    possible_permission
                )
        return PossiblePermissions(
            repository=possible_permissions_dict["repository"],
            account=possible_permissions_dict["user"],
        )
