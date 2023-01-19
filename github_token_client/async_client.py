"""
`async`/`await`-based GitHub token client
"""
from asyncio import Lock
from contextlib import asynccontextmanager
from functools import wraps
from logging import Logger, getLogger
from pathlib import Path
from typing import AsyncIterator, Sequence

from dateutil.parser import isoparse
from playwright.async_api import async_playwright

from .common import (
    AllProjects,
    PasswordError,
    SingleProject,
    TokenListEntry,
    TokenNameError,
    TokenScope,
    TooManyAttemptsError,
    UnexpectedContentError,
    UnexpectedPageError,
    UsernameError,
)
from .credentials import GithubCredentials
from .utils.playwright import launch_ephemeral_chromium_context
from .utils.sequences import one_or_none

default_logger = getLogger(__name__)


def _expect_page(page, expected_url: str):
    if page.url != expected_url:
        raise UnexpectedPageError(
            f"ended up on unexpected page {page.url} (expected {expected_url})"
        )


@asynccontextmanager
async def async_github_token_client(
    credentials: GithubCredentials,
    headless: bool = False,
    persist_to: Path | str | None = None,
    base_url: str = "https://github.com",
    logger: Logger = default_logger,
) -> AsyncIterator["AsyncGithubTokenClientSession"]:
    """
    Context manager for launching an async client session.

    This is the main starting point for using the async client.

    Args:
        credentials: Credentials to log into GitHub with.
        headless: If true, the browser window will not be shown.
        persist_to: Directory in which to persist the browser state. ``None``
            means no persistence.
        base_url: GitHub base URL.
        logger: Logger to log messages to.

    Returns:
      A context manager for the async session.
    """
    async with async_playwright() as p:
        if persist_to is None:
            context = await launch_ephemeral_chromium_context(
                p, headless=headless
            )
        else:
            context = await p.chromium.launch_persistent_context(
                Path(persist_to), headless=headless
            )
        pages = context.pages
        assert len(pages) == 1
        page = pages[0]
        yield AsyncGithubTokenClientSession(
            context, page, credentials, headless, base_url, logger
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

    A session's lifecycle corresponds to that of the browser instance which is
    used to perform operations on the GitHub web interface. When multiple
    operations have to be performed in sequence, it makes sense to do so in the
    a single session to minimize the number of times the browser has to be
    restarted, as this is fairly resource intensive and time consuming.
    """

    def __init__(
        self,
        context,
        page,
        credentials: GithubCredentials,
        headless: bool = True,
        base_url: str = "https://github.com",
        logger: Logger = default_logger,
    ):
        self.context = context
        self.page = page
        self.credentials = credentials
        self.headless = headless
        self.base_url = base_url
        self.logger = logger
        self._lock = Lock()

    async def _get_logged_in_user(self) -> str | None:
        user_button = one_or_none(
            await self.page.locator(
                "#user-indicator > nav:first-child > button"
            ).all()
        )
        if user_button is None:
            return None
        username = (await user_button.inner_text()).strip()
        return username

    async def _handle_login(self) -> bool:
        """
        Automatically handle login if necessary, otherwise do nothing.

        Returns:
            `True` if a login was actually performed, `False` if nothing was
            done.
        """
        logged_in_user = await self._get_logged_in_user()
        if logged_in_user is not None:
            if logged_in_user == self.credentials.username:
                self.logger.info("no login required")
                return False
            else:
                # TODO log out & go to login page
                raise NotImplementedError(
                    f"logged-in user {logged_in_user!r} doesn't match "
                    f"credential username {self.credentials.username!r}, "
                    "which can't be handled yet"
                )
        if not self.page.url.startswith(
            self.base_url.rstrip("/") + "/account/login/"
        ):
            self.logger.info("no login required")
            return False
        username_input = one_or_none(
            await self.page.locator("#username").all()
        )
        if not username_input:
            raise UnexpectedContentError(
                "username field not found on login page"
            )
        password_input = one_or_none(
            await self.page.locator("#password").all()
        )
        if not password_input:
            raise UnexpectedContentError(
                "password field not found on login page"
            )
        await username_input.fill(self.credentials.username)
        await password_input.fill(self.credentials.password)
        async with self.page.expect_event(
            "domcontentloaded"
        ), self.page.expect_navigation():
            self.logger.info("logging in...")
            await password_input.press("Enter")
        if self.page.url.startswith(
            self.base_url.rstrip("/") + "/account/login/"
        ):
            username_errors_or_none = one_or_none(
                await self.page.locator("#username-errors ul li").all()
            )
            username_error = (
                await username_errors_or_none.inner_text()
                if username_errors_or_none is not None
                else None
            )
            if username_error is not None:
                raise UsernameError(username_error)
            password_errors_or_none = one_or_none(
                await self.page.locator("#password-errors ul li").all()
            )
            password_error = (
                await password_errors_or_none.inner_text()
                if password_errors_or_none is not None
                else None
            )
            if password_error is not None:
                if "too many unsuccessful login attempts" in password_error:
                    raise TooManyAttemptsError(password_error)
                else:
                    raise PasswordError(password_error)
        return True

    async def _confirm_password(self):
        confirm_heading = one_or_none(
            await self.page.get_by_text("Confirm password to continue").all()
        )
        if not confirm_heading:
            self.logger.info("no password confirmation required")
            return
        password_input = one_or_none(
            await self.page.locator("#password").all()
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

    async def wait_until_closed(self):
        """
        Wait until the user closes the browser if it's not headless.

        Has no effect and returns immediately in headless mode.
        """

        await self.page.wait_for_event("close", timeout=0)

    @_with_lock
    async def create_token(self, name: str, scope: TokenScope) -> str:
        """
        Create a new token on GitHub.

        Args:
            name: Name of the token to create.
            scope: The token's desired scope.

        Returns:
            The created token.
        """
        # validate & extract from args
        if isinstance(scope, AllProjects):
            scope_selector_value = "scope:user"
        elif isinstance(scope, SingleProject):
            scope_selector_value = f"scope:project:{scope.name}"
        else:
            raise TypeError(f"invalid token scope: {scope}")
        # /validate args
        await self.page.goto(
            self.base_url + "/manage/account/token/",
            wait_until="domcontentloaded",
        )
        # login if necessary
        await self._handle_login()
        # confirm password if necessary
        await self._confirm_password()
        # fill in token name field
        name_input = one_or_none(await self.page.locator("#description").all())
        if name_input is None:
            raise UnexpectedContentError("no token name field found on page")
        await name_input.fill(name)
        # select token scope => project only
        scope_selector = one_or_none(
            await self.page.locator("#token_scope").all()
        )
        if scope_selector is None:
            raise UnexpectedContentError("no scope selector found on page")
        await scope_selector.select_option(value=scope_selector_value)
        async with self.page.expect_event(
            "domcontentloaded"
        ), self.page.expect_navigation():
            self.logger.info(f"creating token {name!r}...")
            await name_input.press("Enter")
        name_errors_or_none = one_or_none(
            await self.page.locator("#token-name-errors ul li").all()
        )
        name_error = (
            await name_errors_or_none.inner_text()
            if name_errors_or_none is not None
            else None
        )
        if name_error is not None:
            raise TokenNameError(name_error)
        token_block = one_or_none(
            await self.page.locator("#provisioned-key > code").all()
        )
        if not token_block:
            raise UnexpectedContentError("no token block found on page")
        token = await token_block.inner_text()
        return token

    @_with_lock
    async def login(self) -> bool:
        """
        Log into GitHub if necessary.

        Normally, this does not need to be called explicitly as all other
        methods in this class perform logins automatically.

        One use case for this is to find out whether the given credentials are
        correct without doing anything else. It should however be noted that an
        actual login will only be performed when necessary, i.e. when the
        session's current state (resulting from loaded persistent browser state
        or prior actions) isn't already logged in.

        Returns:
            `True` if a login was actually performed, `False` if nothing was
            done.
        """
        await self.page.goto(
            self.base_url + "/account/login/",
            wait_until="domcontentloaded",
        )
        # login if necessary
        return await self._handle_login()

    @_with_lock
    async def get_token_list(self) -> Sequence[TokenListEntry]:
        """
        Get list of tokens for the logged-in account on GitHub.

        Returns:
            List of tokens.
        """
        await self.page.goto(
            self.base_url + "settings/tokens?type=beta",
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
        token_list = []
        for row in token_rows:
            cols = await row.locator("th,td").all()
            name = await cols[0].inner_text()
            scope_str = await cols[1].inner_text()
            scope = (
                AllProjects()
                if scope_str == "All projects"
                else SingleProject(scope_str)
            )
            created = isoparse(
                await one_or_none(
                    await cols[2].locator("time").all()
                ).get_attribute("datetime")
            )
            last_used_time_elem = one_or_none(
                await cols[3].locator("time").all()
            )
            last_used = (
                isoparse(await last_used_time_elem.get_attribute("datetime"))
                if last_used_time_elem is not None
                else None
            )
            entry = TokenListEntry(name, scope, created, last_used)
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
