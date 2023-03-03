"""
`async`/`await`-based GitHub token client
"""
import asyncio
from asyncio import Lock
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from functools import wraps
from logging import Logger, getLogger
from pathlib import Path
from typing import AsyncIterator, Sequence, Type, TypeVar

import aiohttp
import dateparser
from bs4 import BeautifulSoup

from .common import (
    AllRepositories,
    FineGrainedTokenMinimalInfo,
    FineGrainedTokenScope,
    FineGrainedTokenStandardInfo,
    LoginError,
    PublicRepositories,
    RepositoryNotFoundError,
    SelectRepositories,
    TokenCreationError,
    TokenNameAlreadyTakenError,
    UnexpectedContentError,
    UnexpectedPageError,
)
from .credentials import GithubCredentials
from .persisting_http_session import PersistingHttpClientSession
from .response_holding_http_session import ResponseHoldingHttpSession
from .utils.sequences import one_or_none

default_logger = getLogger(__name__)

ALL_PERMISSION_NAMES = [
    "actions",
    "administration",
    "security_events",
    "codespaces",
    "codespaces_lifecycle_admin",
    "codespaces_metadata",
    "codespaces_secrets",
    "statuses",
    "contents",
    "vulnerability_alerts",
    "dependabot_secrets",
    "deployments",
    "discussions",
    "environments",
    "issues",
    "merge_queues",
    "metadata",
    "pages",
    "pull_requests",
    "repository_announcement_banners",
    "secret_scanning_alerts",
    "secrets",
    "actions_variables",
    "repository_hooks",
    "workflows",
    "blocking",
    "codespaces_user_secrets",
    "emails",
    "followers",
    "gpg_keys",
    "gists",
    "keys",
    "interaction_limits",
    "plan",
    "private_repository_invitations",
    "profile",
    "git_signing_ssh_public_keys",
    "starring",
    "watching",
]


class PermissionValue(Enum):
    NONE = ""
    READ = "read"
    WRITE = "write"


@dataclass
class _FineGrainedTokenMinimalInternalInfo(FineGrainedTokenMinimalInfo):
    """
    Internally useful information on a fine-grained token from one request.
    """

    deletion_authenticity_token: str


@asynccontextmanager
async def async_github_fine_grained_token_client(
    credentials: GithubCredentials,
    persist_to: Path | None = None,
    base_url: str = "https://github.com",
    logger: Logger = default_logger,
) -> AsyncIterator["AsyncGithubFineGrainedTokenClientSession"]:
    """
    Context manager for launching an async client session.

    This is the main starting point for using the async client.

    Args:
        credentials: Credentials to log into GitHub with.
        persist_to: Directory in which to persist the session state (currently
            just cookies). Will also be used to load previously persisted
            sessions. ``None`` means no persistence.
        base_url: GitHub base URL.
        logger: Logger to log messages to.

    Returns:
      A context manager for the async session.
    """
    async with aiohttp.ClientSession(raise_for_status=True) as http_session:
        yield AsyncGithubFineGrainedTokenClientSession.make_with_cookies_loaded(
            http_session, credentials, persist_to, base_url, logger
        )


def _with_lock(meth):
    @wraps(meth)
    async def _with_lock(self, *args, **kwargs):
        async with self._lock:
            return await meth(self, *args, **kwargs)

    return _with_lock


T = TypeVar("T")


class AsyncGithubFineGrainedTokenClientSession:
    """
    Async token client session.

    Should not be instantiated directly but only through
    :func:`async_github_token_client`.

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
        persist_to: Path | None = None,
        base_url: str = "https://github.com",
        logger: Logger = default_logger,
    ):
        self.inner_http_session = http_session
        if persist_to is not None:
            http_session = PersistingHttpClientSession(
                http_session, persist_to
            )
        self.http_session = ResponseHoldingHttpSession(http_session)
        self.credentials = credentials
        self.base_url = base_url
        self.logger = logger
        self._lock = Lock()

    @property
    def _response(self) -> aiohttp.ClientResponse | None:
        """
        The last received response, if any.
        """
        return self.http_session.response

    @property
    def _persisting_http_session(self) -> PersistingHttpClientSession | None:
        """
        The persisting HTTP session, if any.
        """
        if isinstance(self.http_session.inner, PersistingHttpClientSession):
            return self.http_session.inner
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

    async def _get_parsed_response_html(
        self, response: aiohttp.ClientResponse | None = None
    ) -> BeautifulSoup:
        if response is None:
            response = self._response
        assert response is not None
        response_text = await response.text()
        return BeautifulSoup(response_text, "html.parser")

    def _get_authenticity_token(
        self, html: BeautifulSoup, form_id: str | None = None
    ) -> str:
        selection_str = 'input[name="authenticity_token"]'
        if form_id:
            selection_str = f'form[id="{form_id}"] ' + selection_str
        authenticity_token = (
            one_or_none(html.select(selection_str)) or {}
        ).get("value")
        if authenticity_token is None:
            raise UnexpectedContentError("no authenticity token found on page")
        return authenticity_token

    async def _handle_login(self) -> bool:
        """
        Automatically handle login if necessary, otherwise do nothing.

        Returns:
            `True` if a login was actually performed, `False` if nothing was
            done.
        """
        response = self._response
        assert response is not None
        if not str(response.url).startswith(
            self.base_url.rstrip("/") + "/login"
        ):
            self.logger.info("no login required")
            return False
        else:
            self.logger.info("login required")
        destination_url = response.url.query.get("return_to")
        html = await self._get_parsed_response_html()
        hidden_inputs = {
            input_elem["name"]: input_elem["value"]
            for input_elem in html.select('form input[type="hidden"]')
            if "value" in input_elem.attrs
        }
        await self.http_session.post(
            self.base_url.rstrip("/") + "/session",
            data={
                "login": self.credentials.username,
                "password": self.credentials.password,
                **hidden_inputs,
            },
        )
        if str(self._response.url).startswith(
            self.base_url.rstrip("/") + "/session"
        ):
            login_response_html = await self._get_parsed_response_html()
            login_error = one_or_none(
                login_response_html.select("#js-flash-container")
            )
            if login_error is not None:
                raise LoginError(login_error.get_text().strip())
            raise UnexpectedContentError(
                "ended up back on login page but not sure why"
            )
        if (
            destination_url is not None
            and str(self._response.url) != destination_url
        ):
            raise UnexpectedPageError(
                f"ended up on unexpected page {self._response.url} after login"
                f" (expected {destination_url})"
            )
        return True

    async def _confirm_password(self) -> None:
        html = await self._get_parsed_response_html()
        confirm_access_heading = one_or_none(html.select("#sudo > div > h1"))
        if confirm_access_heading is None:
            self.logger.info("no password confirmation required")
            return
        else:
            self.logger.info("password confirmation required")
        # TODO put this in helper method with form tree as arg
        hidden_inputs = {
            input_elem["name"]: input_elem["value"]
            for input_elem in html.select('form input[type="hidden"]')
        }
        response = await self.http_session.post(
            (
                form_action
                if any(
                    (form_action := html.form["action"]).startswith(scheme)
                    for scheme in ["https://", "http://"]
                )
                else self.base_url.rstrip("/") + form_action
            ),
            data={
                "sudo_password": self.credentials.password,
                **hidden_inputs,
            },
            headers={"Referer": str(self.http_session.response.url)},
        )
        if str(response.url).startswith(
            self.base_url.rstrip("/") + "/sessions/sudo"
        ):
            login_response_text = await response.text()
            login_response_html = BeautifulSoup(
                login_response_text, "html.parser"
            )
            login_error = one_or_none(
                login_response_html.select("#js-flash-container")
            )
            if login_error is not None:
                raise LoginError(login_error.get_text().strip())
            raise UnexpectedContentError(
                "ended up back on login page but not sure why"
            )

    async def _get_repository_id(
        self, target_name: str, repository_name: str
    ) -> int:
        await self.http_session.get(
            self.base_url.rstrip("/")
            + "/settings/personal-access-tokens/suggestions",
            params={"target_name": target_name, "q": repository_name},
        )
        html = await self._get_parsed_response_html()
        for button_elem in html.select("button"):
            input_elem = one_or_none(button_elem.select("input"))
            name_elem = one_or_none(
                button_elem.select(".select-menu-item-text")
            )
            if name_elem is None:
                continue
            name = name_elem.contents[1].get_text()[1:]
            if name == repository_name:
                return int(input_elem["value"])
        raise RepositoryNotFoundError(
            f"no such repository: {target_name}/{repository_name}"
        )

    @_with_lock
    async def create_token(
        self,
        name: str,
        expires: date | timedelta,
        description: str = "",
        resource_owner: str | None = None,
        scope: FineGrainedTokenScope = PublicRepositories(),
        permissions: Mapping[str, PermissionValue] | None = None,
    ) -> str:
        """
        Create a new fine-grained token on GitHub.

        Args:
            name: Name of the token to create.
            expires: Expiration date of the token to create. GitHub currently
                only allows expiration dates up to 1 year in the future.
            description: Description of the token to create.
            resource_owner: Owner of the token to create. Defaults to whatever
                GitHub selects by default (always logged-in user I guess).
            scope: The token's desired scope.
            permissions: Permissions the token should have. Must be a mapping
                from elements of ``ALL_PERMISSION_NAMES`` to the desired value.

        Returns:
            The created token.
        """
        # normalize args
        expires_date = (
            date.today() + expires
            if isinstance(expires, timedelta)
            else expires
        )
        if permissions is None:
            permissions = {}
        # /normalize args
        await self.http_session.get(
            self.base_url.rstrip("/") + "/settings/personal-access-tokens/new"
        )
        # login if necessary
        await self._handle_login()
        # confirm password if necessary
        await self._confirm_password()
        # get dynamic form data
        html = await self._get_parsed_response_html()
        authenticity_token = self._get_authenticity_token(
            html, form_id="new_user_programmatic_access"
        )
        # build form data & submit
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
                await self._get_repository_id(
                    self.credentials.username,  # TODO configurable
                    repository_name,
                )
                for repository_name in scope.names
            ]
        else:
            raise ValueError(f"invalid scope {scope}")
        await self.http_session.post(
            self.base_url.rstrip("/") + "/settings/personal-access-tokens",
            data={
                "authenticity_token": authenticity_token,
                "user_programmatic_access[name]": name,
                "user_programmatic_access[default_expires_at]": "custom",
                "user_programmatic_access[custom_expires_at]": (
                    expires_date.strftime("%Y-%m-%d")
                ),
                "user_programmatic_access[description]": description,
                "target_name": self.credentials.username,  # TODO configurable
                "install_target": install_target,
                "repository_ids[]": repository_ids,
                **{
                    f"integration[default_permissions][{permission_name}]": (
                        permissions.get(
                            permission_name, PermissionValue.NONE
                        ).value
                    )
                    for permission_name in ALL_PERMISSION_NAMES
                },
            },
        )
        # confirm password again if necessary (rare but can happen)
        # TODO unsure if we have to re-send the form data in this case...
        await self._confirm_password()
        # get value of newly created token
        html = await self._get_parsed_response_html()
        token_elem = one_or_none(html.select("#new-access-token"))
        if token_elem is None:
            error_elem = one_or_none(html.select(".error"))
            if error_elem:
                error = error_elem.get_text()
                if "name has already been taken" in error.lower():
                    raise TokenNameAlreadyTakenError(error.lower())
                raise TokenCreationError(f"error creating token: {error}")
            raise UnexpectedContentError("no token value found on page")
        token_value = token_elem["value"]
        return token_value

    @_with_lock
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
            `True` if a login was actually performed, `False` if nothing was
            done.
        """
        await self.http_session.get(self.base_url.rstrip("/") + "/login")
        # login if necessary
        return await self._handle_login()

    @_with_lock
    async def get_tokens_minimal(
        self,
    ) -> Sequence[FineGrainedTokenMinimalInfo]:
        """
        Get fine-grained token list and some information via a single request.

        Note that the returned information does not include the expiration
        date, which would require additional HTTP requests to fetch. To
        retrieve tokens and their expiration dates, you can use
        ``get_tokens`` instead.

        Returns:
            List of tokens.
        """
        # the point of this method is just to add a lock around this one:
        return await self._get_tokens_minimal()

    async def _get_tokens_minimal(
        self,
    ) -> Sequence[FineGrainedTokenMinimalInfo]:
        return [
            FineGrainedTokenMinimalInfo(
                id=info.id, name=info.name, last_used_str=info.last_used_str
            )
            for info in await self._get_tokens_minimal_internal()
        ]

    async def _get_tokens_minimal_internal(
        self,
    ) -> Sequence[_FineGrainedTokenMinimalInternalInfo]:
        await self.http_session.get(
            self.base_url.rstrip("/") + "/settings/tokens?type=beta"
        )
        # login if necessary
        await self._handle_login()
        # confirm password if necessary
        await self._confirm_password()
        # get list
        html = await self._get_parsed_response_html()
        listgroup_elem = one_or_none(html.select(".listgroup"))
        if not listgroup_elem:
            raise UnexpectedContentError("no token list found on page")
        token_elems = html.select(
            ".listgroup > .access-token > .listgroup-item"
        )
        token_list = []
        for token_elem in token_elems:
            last_used_str = (
                one_or_none(token_elem.select(".last-used")).get_text().strip()
            )
            details_link = one_or_none(
                token_elem.select(".token-description > strong a")
            )
            id_ = int(details_link["href"].split("/")[-1])
            name = details_link.get_text().strip()
            deletion_authenticity_token = self._get_authenticity_token(
                token_elem
            )
            entry = _FineGrainedTokenMinimalInternalInfo(
                id=id_,
                name=name,
                last_used_str=last_used_str,
                deletion_authenticity_token=deletion_authenticity_token,
            )
            token_list.append(entry)
        return token_list

    @_with_lock
    async def get_token_expiration(self, token_id: int) -> datetime:
        """
        Retrieve the expiration date of a single fine-grained token.

        Args:
            token_id: The fine-grained token's ID.

        Returns:
            The fine-grained token's expiration date.
        """
        # the point of this method is just to add a lock around this one:
        return self._get_token_expiration()

    async def _get_token_expiration(self, token_id: int) -> datetime:
        # NOTE: no lock (efficiency)! => don't rely on self._response
        response = await self.http_session.get(
            self.base_url.rstrip("/")
            + f"/settings/personal-access-tokens/{token_id}/expiration?page=1"
        )
        html = await self._get_parsed_response_html(response)
        expires_str = html.get_text().strip()
        if any(
            expires_str.lower().startswith(x)
            for x in ("expires on ", "expired on ")
        ):
            expires_str = expires_str[len("expire* on ") :]
        return dateparser.parse(expires_str)

    @_with_lock
    async def get_tokens(
        self,
    ) -> Sequence[FineGrainedTokenStandardInfo]:
        """
        Get list of fine-grained tokens with all data shown on the tokens page.

        This has to make one additional HTTP request for each token to get its
        expiration date (this is also how it works on GitHub's fine-grained
        tokens page), so it will be a bit slower than
        ``get_tokens_minimal``.

        Returns:
            List of tokens.
        """
        summaries = await self._get_tokens_minimal()
        fetch_expiration_tasks = [
            asyncio.create_task(self._get_token_expiration(summary.id))
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

    @_with_lock
    async def delete_token(self, name: str) -> None:
        """
        Delete fine-grained token from GitHub.

        Args:
            name: Name of the token to delete.
        """
        # get list first because each has its own deletion authenticity token
        info_by_name = {
            info.name: info
            for info in await self._get_tokens_minimal_internal()
        }
        if name not in info_by_name:
            raise KeyError(f"no such token: {name!r}")
        # delete
        id_ = info_by_name[name].id
        self.logger.info(f"deleting token {name!r}")
        await self.http_session.post(
            self.base_url.rstrip("/")
            + f"/settings/personal-access-tokens/{id_}",
            data={
                "_method": "delete",
                "authenticity_token": (
                    info_by_name[name].deletion_authenticity_token
                ),
            },
            headers={
                "Referer": (
                    self.base_url.rstrip("/") + "/settings/tokens?type=beta"
                )
            },
        )
        # confirm password if necessary
        html = await self._get_parsed_response_html()
        await self._confirm_password()
        # check that it worked
        html = await self._get_parsed_response_html()
        alert = html.select_one('div[role="alert"]')
        if alert is None:
            raise UnexpectedContentError("deletion result not found on page")
        alert_text = alert.get_text().strip()
        if not alert_text == "Deleted personal access token":
            raise UnexpectedContentError(f"deletion failed: {alert_text!r}")
        self.logger.info(f"deleted token {name!r}")
