import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from itertools import count
from pathlib import Path
from pprint import pprint
from traceback import print_exc

from .async_client import AsyncGithubTokenClientSession, async_github_token_client
from .common import PasswordError, TokenScope, UsernameError
from .credentials import (
    get_credentials_from_keyring_and_prompt,
    prompt_for_credentials,
    save_credentials_to_keyring,
)

max_login_attempts = 3


class App:
    def __init__(
        self,
        headless: bool = True,
        persist_to: Path | None = None,
        username: str | None = None,
        password: str | None = None,
        github_base_url: str = "https://github.com",
    ):
        self.headless = headless
        self.persist_to = persist_to
        self.username = username
        self.password = password
        self.github_base_url = github_base_url

    @asynccontextmanager
    async def _logged_in_session(
        self,
    ) -> AsyncIterator[AsyncGithubTokenClientSession]:
        # don't do anything interactive (e.g. ask about saving to keyring or
        # retry with prompt) if both username and password are provided
        # (generally suggests no interactivity is desired)
        interactive = self.username is None or self.password is None
        (
            credentials,
            credentials_are_new,
        ) = get_credentials_from_keyring_and_prompt(
            self.github_base_url, self.username, self.password
        )
        async with async_github_token_client(
            credentials, self.headless, self.persist_to, self.github_base_url
        ) as session:
            for attempt in count():
                try:
                    did_login = await session.login()
                    if did_login and credentials_are_new and interactive:
                        save = input(
                            "success! save credentials to keyring (Y/n)? "
                        )
                        if save == "Y":
                            save_credentials_to_keyring(
                                self.github_base_url, credentials
                            )
                            print("saved")
                        else:
                            print("not saving")
                    break
                except (UsernameError, PasswordError) as e:
                    print(f"Login failed: {e}")
                    if attempt >= max_login_attempts or not interactive:
                        print("Giving up.")
                        raise
                    credentials = prompt_for_credentials()
                    credentials_are_new = True
                    session.credentials = credentials
            yield session

    @staticmethod
    @asynccontextmanager
    async def _handle_errors(session: AsyncGithubTokenClientSession):
        try:
            yield
        except Exception:
            print_exc()
            if session.headless:
                print(
                    "If you want to see what exactly went wrong by looking at "
                    "the browser window, rerun in non-headless mode"
                )
            else:
                print_exc()
                print(
                    "check browser window for what exactly went wrong "
                    "and close it once done"
                )
                await session.wait_until_closed()
            exit(1)

    @asynccontextmanager
    async def _logged_in_error_handling_session(
        self,
    ) -> AsyncIterator[AsyncGithubTokenClientSession]:
        async with self._logged_in_session() as session, self._handle_errors(
            session
        ):
            yield session

    def create_token(self, token_name: str, scope: TokenScope) -> None:
        async def _run():
            async with self._logged_in_error_handling_session() as session:
                token = await session.create_token(token_name, scope)
            print("Created token:")
            print(token)

        asyncio.run(_run())

    def list_tokens(self) -> None:
        async def _run():
            async with self._logged_in_error_handling_session() as session:
                tokens = await session.get_token_list()
            pprint(tokens)

        asyncio.run(_run())

    def delete_token(
        self,
        name: str,
    ) -> None:
        async def _run():
            async with self._logged_in_error_handling_session() as session:
                await session.delete_token(name)

        asyncio.run(_run())
