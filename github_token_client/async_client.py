"""
`async`/`await`-based GitHub token client
"""
import asyncio
from asyncio import Lock
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from functools import wraps
from logging import Logger, getLogger
from pathlib import Path
from typing import AsyncIterator, Sequence, Type, TypeVar

import aiohttp
import dateparser
from bs4 import BeautifulSoup

from github_token_client.persisting_http_session import (
    PersistingHttpClientSession,
)
from github_token_client.response_holding_http_session import (
    ResponseHoldingHttpSession,
)

from .common import (
    AllRepositories,
    ClassicTokenStandardInfo,
    FineGrainedTokenMinimalInfo,
    FineGrainedTokenScope,
    FineGrainedTokenStandardInfo,
    LoginError,
    PublicRepositories,
    SelectRepositories,
    UnexpectedContentError,
)
from .credentials import GithubCredentials
from .utils.sequences import one_or_none

default_logger = getLogger(__name__)


@asynccontextmanager
async def async_github_token_client(
    credentials: GithubCredentials,
    persist_to: Path | None = None,
    base_url: str = "https://github.com",
    logger: Logger = default_logger,
) -> AsyncIterator["AsyncGithubTokenClientSession"]:
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
    async with aiohttp.ClientSession() as http_session:
        yield AsyncGithubTokenClientSession.make_with_cookies_loaded(
            http_session, credentials, persist_to, base_url, logger
        )


def _with_lock(meth):
    @wraps(meth)
    async def _with_lock(self, *args, **kwargs):
        async with self._lock:
            return await meth(self, *args, **kwargs)

    return _with_lock


T = TypeVar("T")


class AsyncGithubTokenClientSession:
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
        obj.load_cookies()
        return obj

    def load_cookies(self):
        """
        Load cookies from persistence location (if any) into HTTP session.
        """
        if self._persisting_http_session is not None:
            self._persisting_http_session.load()

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
        response_text = await response.text()
        html = BeautifulSoup(response_text, "html.parser")
        authenticity_token = (
            one_or_none(html.select('input[name="authenticity_token"]')) or {}
        ).get("value")
        if authenticity_token is None:
            raise UnexpectedContentError("no authenticity token found on page")
        response = await self.http_session.post(
            self.base_url.rstrip("/") + "/session",
            data={
                "login": self.credentials.username,
                "password": self.credentials.password,
                "authenticity_token": authenticity_token,
            },
        )
        if str(response.url).startswith(
            self.base_url.rstrip("/") + "/session"
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
        return True

    async def _confirm_password(self) -> None:
        response = self._response
        assert response is not None
        response_text = await response.text()
        html = BeautifulSoup(response_text, "html.parser")
        confirm_access_heading = one_or_none(html.select("#sudo > div > h1"))
        if confirm_access_heading is None:
            self.logger.info("no password confirmation required")
            return
        else:
            self.logger.info("password confirmation required")
        authenticity_token = (
            one_or_none(html.select('input[name="authenticity_token"]')) or {}
        ).get("value")
        if authenticity_token is None:
            raise UnexpectedContentError("no authenticity token found on page")
        response = await self.http_session.post(
            self.base_url.rstrip("/") + "/session",
            data={
                "sudo_password": self.credentials.password,
                "authenticity_token": authenticity_token,
                "sudo_return_to": response.url,
                "credential_type": "password",
            },
        )
        if str(response.url).startswith(
            self.base_url.rstrip("/") + "/session"
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
        return True

    @_with_lock
    async def create_fine_grained_token(
        self,
        name: str,
        expires: date | timedelta,
        description: str = "",
        resource_owner: str | None = None,
        scope: FineGrainedTokenScope = PublicRepositories(),
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

        Returns:
            The created token.
        """
        # normalize args
        if isinstance(expires, timedelta):
            expires_date = date.today() + expires
        # /normalize args
        await self.page.goto(
            self.base_url + "/settings/personal-access-tokens/new",
            wait_until="domcontentloaded",
        )
        # login if necessary
        await self._handle_login()
        # confirm password if necessary
        await self._confirm_password()
        # fill in token name field
        name_input = one_or_none(
            await self.page.get_by_label("Token name").all()
        )
        if name_input is None:
            raise UnexpectedContentError("no token name field found on page")
        await name_input.fill(name)
        # set expiration date
        # select custom date
        (
            expiration_select_input,
            expiration_date_input,
        ) = await self.page.get_by_label("Expiration").all()
        await expiration_select_input.select_option(value="custom")
        # set custom date
        await expiration_date_input.wait_for(state="visible", timeout=5000)
        await expiration_date_input.type(expires_date.strftime("%m%d%Y"))
        # select token scope
        if isinstance(scope, PublicRepositories):
            scope_label = "Public Repositories (read-only)"
        elif isinstance(scope, AllRepositories):
            scope_label = "All repositories"
        elif isinstance(scope, SelectRepositories):
            scope_label = "Only select repositories"
        else:
            raise TypeError(f"invalid token scope: {scope}")
        scope_radio_button = one_or_none(
            await self.page.get_by_label(scope_label).all()
        )
        if scope_radio_button is None:
            raise UnexpectedContentError(
                f"no scope radio button for label {scope_label!r} "
                "found on page"
            )
        await scope_radio_button.click()
        # with select repository scoped tokens, we have to select them from the
        # dropdown menu that appears
        if isinstance(scope, SelectRepositories):
            select_repositories_dropdown_loc = self.page.locator(
                "summary > span"
            ).filter(has_text="Select repositories")
            await select_repositories_dropdown_loc.wait_for(
                state="visible", timeout=5000
            )
            select_repositories_dropdown = one_or_none(
                await select_repositories_dropdown_loc.all()
            )
            if select_repositories_dropdown is None:
                raise UnexpectedContentError(
                    "no dropdown menu to select repositories from "
                    "found on page"
                )
            await select_repositories_dropdown.click()
            repo_search_input_loc = self.page.get_by_placeholder(
                "Search for a repository"
            )
            await repo_search_input_loc.wait_for(state="visible", timeout=5000)
            repo_search_input = one_or_none(await repo_search_input_loc.all())
            if repo_search_input is None:
                raise UnexpectedContentError(
                    "no repository search input found on page"
                )
            for repo_name in scope.names:
                await repo_search_input.type(repo_name)
                repo_list = await self.page.locator(
                    "#repository-menu-list > button"
                ).all()
                await asyncio.sleep(1000)  # TODO wait for list entries
                if len(repo_list) > 1:
                    raise NotImplementedError(
                        "selecting one of multiple repos not yet implemented"
                    )
                await repo_search_input.press("ArrowDown")
                await repo_search_input.press("Enter")
        await asyncio.sleep(20)
        # TODO
        return "not yet implemented"

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
    async def get_fine_grained_tokens_minimal(
        self,
    ) -> Sequence[FineGrainedTokenMinimalInfo]:
        """
        Get fine-grained token list and some information via a single request.

        Note that the returned information does not include the expiration
        date, which would require additional HTTP requests to fetch. To
        retrieve tokens and their expiration dates, you can use
        ``get_fine_grained_tokens`` instead.

        Returns:
            List of tokens.
        """
        # the point of this method is just to add a lock around this one:
        return await self._get_fine_grained_tokens_minimal()

    async def _get_fine_grained_tokens_minimal(
        self,
    ) -> Sequence[FineGrainedTokenMinimalInfo]:
        await self.http_session.get(
            self.base_url.rstrip("/") + "/settings/tokens?type=beta"
        )
        # login if necessary
        await self._handle_login()
        # confirm password if necessary
        await self._confirm_password()
        # get list
        response_text = await self._response.text()
        html = BeautifulSoup(response_text, "html.parser")
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
            # these are loaded with JS:
            # TODO fetch separately?
            # TODO handle expired tokens (unsure yet how that looks)
            # expires_loc = token_loc.locator(".text-italic")
            # await expires_loc.wait_for(state="visible", timeout=5000)
            # expires_str = await one_or_none(
            # await expires_loc.all()
            # ).inner_text()
            # if expires_str.startswith("on "):
            # expires_str = expires_str[2:]
            # expires = dateparser.parse(expires_str)
            # if expires is None:
            # raise ValueError(
            # "could not parse expiration date {expires_str!r}"
            # )
            entry = FineGrainedTokenMinimalInfo(
                id=id_, name=name, last_used_str=last_used_str
            )
            token_list.append(entry)
        return token_list

    @_with_lock
    async def get_classic_tokens(
        self,
    ) -> Sequence[ClassicTokenStandardInfo]:
        """
        Get list of classic tokens with all data shown on the tokens page.

        Returns:
            List of tokens.
        """
        await self.http_session.get(
            self.base_url.rstrip("/") + "/settings/tokens"
        )
        # login if necessary
        await self._handle_login()
        # confirm password if necessary
        await self._confirm_password()
        # get list
        response_text = await self._response.text()
        html = BeautifulSoup(response_text, "html.parser")
        token_elems = html.select(
            ".listgroup > .access-token > .listgroup-item"
        )
        token_list = []
        for token_elem in token_elems:
            last_used_str = (
                one_or_none(token_elem.select(".last-used")).get_text().strip()
            )
            details_link = one_or_none(
                token_elem.select(".token-description > strong > a")
            )
            id_ = int(details_link["href"].split("/")[-1])
            name = details_link.get_text().strip()
            # in contrast to the fine-grained ones, these are static HTML so we
            # don't have to wait for them to be loaded:
            expires_str = token_elem.contents[7].get_text().strip()
            # XXX ^ 4th tag actually but BS counts space in between as
            # children...
            if any(
                expires_str.lower().startswith(x)
                for x in ("expires on ", "expired on ")
            ):
                expires_str = expires_str[len("expire* on ") :]
            expires = dateparser.parse(expires_str)
            entry = ClassicTokenStandardInfo(
                id=id_, name=name, expires=expires, last_used_str=last_used_str
            )
            token_list.append(entry)
        return token_list

    @_with_lock
    async def get_fine_grained_token_expiration(
        self, token_id: int
    ) -> datetime:
        """
        Retrieve the expiration date of a single fine-grained token.

        Args:
            token_id: The fine-grained token's ID.

        Returns:
            The fine-grained token's expiration date.
        """
        # the point of this method is just to add a lock around this one:
        return self._get_fine_grained_token_expiration()

    async def _get_fine_grained_token_expiration(
        self, token_id: int
    ) -> datetime:
        # NOTE: no lock (efficiency)! => don't rely on self._response
        response = await self.http_session.get(
            self.base_url
            + f"/settings/personal-access-tokens/{token_id}/expiration?page=1"
        )
        response_text = await response.text()
        html = BeautifulSoup(response_text, "html.parser")
        expires_str = html.get_text().strip()
        if any(
            expires_str.lower().startswith(x)
            for x in ("expires on ", "expired on ")
        ):
            expires_str = expires_str[len("expire* on ") :]
        return dateparser.parse(expires_str)

    @_with_lock
    async def get_fine_grained_tokens(
        self,
    ) -> Sequence[FineGrainedTokenStandardInfo]:
        """
        Get list of fine-grained tokens with all data shown on the tokens page.

        This has to make one additional HTTP request for each token to get its
        expiration date (this is also how it works on GitHub's fine-grained
        tokens page), so it will be a bit slower than
        ``get_fine_grained_tokens_minimal``.

        Returns:
            List of tokens.
        """
        summaries = await self._get_fine_grained_tokens_minimal()
        fetch_expiration_tasks = [
            asyncio.create_task(
                self._get_fine_grained_token_expiration(summary.id)
            )
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
    async def delete_token(self, name: str):
        """
        Delete token on GitHub.

        Args:
            name: Name of the token to delete.
        """
        await self.page.goto(
            self.base_url + "/manage/account/",
            wait_until="domcontentloaded",
        )
        # login if necessary
        await self._handle_login()
        # confirm password if necessary
        await self._confirm_password()
        # get list
        token_rows = await self.page.locator(
            "#api-tokens > table > tbody > tr"
        ).all()
        for row in token_rows:
            cols = await row.locator("th,td").all()
            listed_name = await cols[0].inner_text()
            if listed_name != name:
                continue
            options_button = one_or_none(
                await cols[4]
                .locator("nav > button")
                .get_by_text("Options", exact=True)
                .all()
            )
            if options_button is None:
                raise UnexpectedContentError(
                    "no options button found for token"
                )
            await options_button.click()
            remove_button = (
                cols[4].locator("nav a").get_by_text("Remove token")
            )
            await remove_button.wait_for(state="visible", timeout=5000)
            await remove_button.click()
            confirm_dialog_heading = self.page.get_by_text(
                f"Remove API token - {name}", exact=True
            )
            confirm_dialog = self.page.locator(
                'div[role="dialog"]', has=confirm_dialog_heading
            )
            await confirm_dialog.wait_for(state="visible", timeout=5000)
            password_input = one_or_none(
                await confirm_dialog.locator('input[type="password"]').all()
            )
            if password_input is None:
                raise UnexpectedContentError("no password field found")
            await password_input.fill(self.credentials.password)
            async with self.page.expect_event(
                "domcontentloaded"
            ), self.page.expect_navigation():
                self.logger.info(f"deleting token {name!r}...")
                await password_input.press("Enter")
            await self.page.get_by_text("Deleted API token").wait_for(
                state="visible", timeout=5000
            )
            self.logger.info(f"deleted token {name!r}")
            return
        else:
            self.logger.info(f"no token named {name} found. nothing to do")
            return
