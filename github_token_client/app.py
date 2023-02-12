import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from itertools import count
from pathlib import Path
from pprint import pprint

from .async_client import (
    AsyncGithubTokenClientSession,
    async_github_token_client,
)
from .common import FineGrainedTokenScope, LoginError
from .credentials import (
    get_credentials_from_keyring_and_prompt,
    prompt_for_credentials,
    save_credentials_to_keyring,
)

max_login_attempts = 3


class App:
    def __init__(
        self,
        persist_to: Path | None = None,
        username: str | None = None,
        password: str | None = None,
        github_base_url: str = "https://github.com",
    ):
        self.persist_to = persist_to
        self.username = username
        self.password = password
        self.github_base_url = github_base_url

    @asynccontextmanager
    async def _logged_in_error_handling_session(
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
            credentials, self.persist_to, self.github_base_url
        ) as session, self._handle_errors(session):
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
                except LoginError as e:
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
        # TODO
        yield

    def create_token(
        self, token_name: str, scope: FineGrainedTokenScope
    ) -> None:
        async def _run():
            async with self._logged_in_error_handling_session() as session:
                token = await session.create_fine_grained_token(
                    token_name, timedelta(days=364), "", None, scope
                )
            print("Created token:")
            print(token)

        asyncio.run(_run())

    def list_tokens(self) -> None:
        async def _run():
            async with self._logged_in_error_handling_session() as session:
                classic_tokens = await session.get_classic_tokens()
                fine_grained_tokens = await session.get_fine_grained_tokens()
                tokens = classic_tokens + fine_grained_tokens
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
