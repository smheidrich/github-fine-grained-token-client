"""
`async`/`await`-based GitHub token client
"""
import asyncio
from asyncio import Lock
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import wraps
from logging import Logger, getLogger
from typing import AsyncIterator, Mapping, Sequence

import dateparser
import httpx
from bs4 import BeautifulSoup

from .common import (
    AllRepositories,
    ClassicTokenListEntry,
    FineGrainedTokenListEntry,
    FineGrainedTokenScope,
    LoginError,
    PublicRepositories,
    SelectRepositories,
    UnexpectedContentError,
)
from .credentials import GithubCredentials
from .utils.sequences import one_or_none

default_logger = getLogger(__name__)


@dataclass
class GithubTokenClientSessionState:
    """
    Session state that can be used to preserve logged-in states.

    Re-initializing client session with this and not just credentials can
    reduce the number of unnecessary logins that need to be performed.
    """

    cookies: Mapping[str, str] = field(default_factory=dict)


@asynccontextmanager
async def async_github_token_client(
    credentials: GithubCredentials,
    state: GithubTokenClientSessionState | None = None,
    base_url: str = "https://github.com",
    logger: Logger = default_logger,
) -> AsyncIterator["AsyncGithubTokenClientSession"]:
    """
    Context manager for launching an async client session.

    This is the main starting point for using the async client.

    Args:
        credentials: Credentials to log into GitHub with.
        state: Session state (avoids unnecessary logins).
        base_url: GitHub base URL.
        logger: Logger to log messages to.

    Returns:
      A context manager for the async session.
    """
    async with httpx.AsyncClient(
        **({"cookies": state.cookies} if state is not None else {})
    ) as http_client:
        yield AsyncGithubTokenClientSession(
            http_client, credentials, base_url, logger
        )


def _with_lock(meth):
    @wraps(meth)
    async def _with_lock(self, *args, **kwargs):
        async with self._lock:
            return await meth(self, *args, **kwargs)

    return _with_lock


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
        http_client: httpx.AsyncClient,
        credentials: GithubCredentials,
        base_url: str = "https://github.com",
        logger: Logger = default_logger,
    ):
        self.http_client = http_client
        self.credentials = credentials
        self.base_url = base_url
        self.logger = logger
        self._lock = Lock()

    @property
    def state(self) -> GithubTokenClientSessionState:
        return GithubTokenClientSessionState(cookies=self.http_client.cookies)

    async def _handle_login(self, response: httpx.Response) -> bool:
        """
        Automatically handle login if necessary, otherwise do nothing.

        Returns:
            `True` if a login was actually performed, `False` if nothing was
            done.
        """
        if not str(response.url).startswith(
            self.base_url.rstrip("/") + "/login"
        ):
            self.logger.info("no login required")
            return False
        else:
            self.logger.info("login required")
        html = BeautifulSoup(response.text, "html.parser")
        authenticity_token = (
            one_or_none(html.select('input[name="authenticity_token"]')) or {}
        ).get("value")
        if authenticity_token is None:
            raise UnexpectedContentError("no authenticity token found on page")
        print(authenticity_token)
        login_response = await self.http_client.post(
            self.base_url.rstrip("/") + "/session",
            data={
                "login": self.credentials.username,
                "password": self.credentials.password,
                "authenticity_token": authenticity_token,
            },
            follow_redirects=True,
        )
        if str(login_response.url).startswith(
            self.base_url.rstrip("/") + "/session"
        ):
            login_response_html = BeautifulSoup(login_response, "html.parser")
            login_error = one_or_none(
                login_response_html.select("#js-flash-container")
            )
            if login_error is not None:
                raise LoginError(login_error.get_text().strip())
            raise UnexpectedContentError(
                "ended up back on login page but not sure why"
            )
        return True

    async def _confirm_password(self):
        confirm_heading = one_or_none(
            await self.page.get_by_text("Confirm access").all()
        )
        if not confirm_heading:
            self.logger.info("no password confirmation required")
            return
        password_input = one_or_none(
            await self.page.locator("#sudo_password").all()
        )
        if not password_input:
            raise UnexpectedContentError("no password field found")
            return
        await password_input.fill(self.credentials.password)
        async with self.page.expect_event(
            "domcontentloaded"
        ), self.page.expect_navigation():
            self.logger.info("confirming password...")
            await password_input.press("Enter")

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
        response = await self.http_client.get(
            self.base_url.rstrip("/") + "/login",
            follow_redirects=True,
        )
        # login if necessary
        return await self._handle_login(response)

    @_with_lock
    async def get_fine_grained_token_list(
        self,
    ) -> Sequence[FineGrainedTokenListEntry]:
        """
        Get list of fine-grained tokens for the logged-in account on GitHub.

        Returns:
            List of tokens.
        """
        response = await self.http_client.get(
            self.base_url.rstrip("/") + "/settings/tokens?type=beta"
        )
        # login if necessary
        await self._handle_login(response)
        # confirm password if necessary
        await self._confirm_password()
        # get list
        token_locs = await self.page.locator(
            ".listgroup > .access-token > .listgroup-item"
        ).all()
        token_list = []
        for token_loc in token_locs:
            last_used_str = await one_or_none(
                await token_loc.locator(".last-used").all()
            ).inner_text()
            name = (
                await one_or_none(
                    await token_loc.locator(".token-description").all()
                ).inner_text()
            ).strip()
            # these are loaded with JS:
            # TODO handle expired tokens (unsure yet how that looks)
            expires_loc = token_loc.locator(".text-italic")
            await expires_loc.wait_for(state="visible", timeout=5000)
            expires_str = await one_or_none(
                await expires_loc.all()
            ).inner_text()
            if expires_str.startswith("on "):
                expires_str = expires_str[2:]
            expires = dateparser.parse(expires_str)
            if expires is None:
                raise ValueError(
                    "could not parse expiration date {expires_str!r}"
                )
            entry = FineGrainedTokenListEntry(name, expires, last_used_str)
            token_list.append(entry)
        return token_list

    @_with_lock
    async def get_classic_token_list(
        self,
    ) -> Sequence[ClassicTokenListEntry]:
        """
        Get list of classic tokens for the logged-in account on GitHub.

        Returns:
            List of tokens.
        """
        await self.page.goto(
            self.base_url + "/settings/tokens",
            wait_until="domcontentloaded",
        )
        # login if necessary
        await self._handle_login()
        # confirm password if necessary
        await self._confirm_password()
        # get list
        token_locs = await self.page.locator(
            ".listgroup > .access-token > .listgroup-item"
        ).all()
        token_list = []
        for token_loc in token_locs:
            last_used_str = await one_or_none(
                await token_loc.locator(".last-used").all()
            ).inner_text()
            name = (
                await one_or_none(
                    await token_loc.locator(".token-description").all()
                ).inner_text()
            ).strip()
            # in contrast to the fine-grained ones, these are static HTML so we
            # don't have to wait for them to be loaded:
            expires_loc = token_loc.locator("xpath=*[4]")
            expires_str = await one_or_none(
                await expires_loc.all()
            ).inner_text()
            expires_str = expires_str.strip()
            if any(
                expires_str.lower().startswith(x)
                for x in ("expires on ", "expired on ")
            ):
                expires_str = expires_str[len("expire* on ") :]
            expires = dateparser.parse(expires_str)
            entry = ClassicTokenListEntry(name, expires, last_used_str)
            token_list.append(entry)
        return token_list

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
