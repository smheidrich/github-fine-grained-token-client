import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import fields
from datetime import timedelta
from itertools import count
from pathlib import Path
from typing import Any

from yachalk import chalk

from .async_client import (
    AsyncGithubFineGrainedTokenClientSession,
    PermissionValue,
    async_github_fine_grained_token_client,
)
from .common import FineGrainedTokenScope, LoginError
from .credentials import (
    get_credentials_from_keyring_and_prompt,
    prompt_for_credentials,
    save_credentials_to_keyring,
)
from .dev import PosiblePermissions, PossiblePermission
from .permissions import (
    AccountPermission,
    AnyPermissionKey,
    RepositoryPermission,
)
from .two_factor_authentication import BlockingPromptTwoFactorOtpProvider

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
        self.two_factor_otp_provider = BlockingPromptTwoFactorOtpProvider()

    @asynccontextmanager
    async def _logged_in_error_handling_session(
        self,
    ) -> AsyncIterator[AsyncGithubFineGrainedTokenClientSession]:
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
        async with async_github_fine_grained_token_client(
            credentials=credentials,
            two_factor_otp_provider=self.two_factor_otp_provider,
            persist_to=self.persist_to,
            base_url=self.github_base_url,
        ) as session, self._handle_errors(session):
            for attempt in count():
                try:
                    did_login = await session.login()
                    if did_login and credentials_are_new and interactive:
                        # TODO we never get here if we have a persistence state
                        # with pw confirmed, so deleting pw from keyring while
                        # still having that state means pw will never be saved
                        # and user will be prompted for it on each run => fix?
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
    async def _handle_errors(
        session: AsyncGithubFineGrainedTokenClientSession,
    ):
        # TODO
        yield

    def create_token(
        self,
        token_name: str,
        scope: FineGrainedTokenScope,
        description: str = "",
        permissions: Mapping[AnyPermissionKey, PermissionValue] | None = None,
    ) -> None:
        async def _run():
            async with self._logged_in_error_handling_session() as session:
                token = await session.create_token(
                    token_name,
                    timedelta(days=364),
                    description,
                    None,
                    scope,
                    permissions,
                )
            print("Created token:")
            print(token)

        asyncio.run(_run())

    def list_fetched_possible_permissions(
        self, fetch=False, codegen=False
    ) -> None:
        async def _run():
            if fetch:
                async with self._logged_in_error_handling_session() as session:
                    possible_permissions = (
                        await session.get_possible_permissions()
                    )
            else:
                possible_permissions = PosiblePermissions(
                    account=[
                        PossiblePermission(
                            p.value, p.full_name, "", p.allowed_values
                        )
                        for p in AccountPermission
                    ],
                    repository=[
                        PossiblePermission(
                            p.value, p.full_name, "", p.allowed_values
                        )
                        for p in RepositoryPermission
                    ],
                )
            for group in ["repository", "account"]:
                if codegen:
                    print(f"class {group.capitalize()}Permission(...):")
                    for possible_permission in getattr(
                        possible_permissions, group
                    ):
                        print(
                            f"    {possible_permission.identifier.upper()} = "
                            f'"{possible_permission.identifier}", '
                            f'"{possible_permission.name}", ('
                            + ", ".join(
                                f"PermissionValue.{allowed_value.name}"
                                for allowed_value in (
                                    possible_permission.allowed_values
                                )
                            )
                            + ")"
                        )
                    print()
                else:
                    print(chalk.bold(f"{group.capitalize()}:"))
                    for possible_permission in getattr(
                        possible_permissions, group
                    ):
                        print(
                            f"  {chalk.bold(possible_permission.name)} "
                            f"({possible_permission.identifier})"
                            + (
                                f"\n    {possible_permission.description}"
                                if fetch
                                else ""
                            )
                            + "\n    Possible values: "
                            + ", ".join(
                                allowed_value.value
                                for allowed_value in (
                                    possible_permission.allowed_values
                                )
                                if allowed_value != PermissionValue.NONE
                            )
                        )

        asyncio.run(_run())

    @classmethod
    def _pretty_print_tokens(cls, tokens: Sequence[Any]) -> None:
        """
        Pretty-print tokens to standard output.

        Args:
            tokens: A sequence of token instances (any dataclass instance with
                a name attribute will work).
        """
        for token in tokens:
            print(chalk.bold(token.name))
            for f in fields(token):
                if f.name == "permissions":
                    print(f"  {f.name}:")
                    permissions = getattr(token, f.name)
                    for key, value in permissions.items():
                        if value != PermissionValue.NONE:
                            print(f"    {key.value}: {value.value}")
                    continue
                print(f"  {f.name}: {getattr(token, f.name)}")

    def list_tokens(self) -> None:
        async def _run():
            async with self._logged_in_error_handling_session() as session:
                tokens = await session.get_tokens()
            self._pretty_print_tokens(tokens)

        asyncio.run(_run())

    def show_token_info_by_id(
        self, token_id: int, complete: bool = False
    ) -> bool:
        async def _run():
            async with self._logged_in_error_handling_session() as session:
                if complete:
                    full_token_info = (
                        await session.get_complete_persistent_token_info(
                            token_id
                        )
                    )
                else:
                    full_token_info = await session.get_token_info(token_id)
            self._pretty_print_tokens([full_token_info])
            return True

        return asyncio.run(_run())

    def show_token_info_by_name(
        self, name: str, complete: bool = False
    ) -> bool:
        # TODO refactor: extract commonalities with ^
        async def _run():
            async with self._logged_in_error_handling_session() as session:
                tokens = await session.get_tokens()
                tokens_by_name = {token.name: token for token in tokens}
                try:
                    token = tokens_by_name[name]
                except KeyError:
                    print(f"No token named {name!r} found.")
                    return False
                if complete:
                    full_token_info = (
                        await session.get_complete_persistent_token_info(
                            token.id
                        )
                    )
                else:
                    full_token_info = await session.get_token_info(token.id)
            self._pretty_print_tokens([full_token_info])
            return True

        return asyncio.run(_run())

    def delete_token(self, name: str) -> bool:
        """
        Returns:
            Whether a token of that name was actually deleted or whether
            nothing had to be done because it was missing.
        """

        async def _run():
            async with self._logged_in_error_handling_session() as session:
                await session.delete_token(name)

        try:
            asyncio.run(_run())
            print(f"Deleted token {name!r}")
            return True
        except KeyError:
            print(f"No token named {name!r} found. Nothing to do.")
            return False
