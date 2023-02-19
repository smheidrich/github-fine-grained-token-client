import logging
from dataclasses import dataclass
from pathlib import Path
from sys import stderr

import typer
from github_token_client.async_client import PermissionValue

from github_token_client.common import (
    AllRepositories,
    PublicRepositories,
    SelectRepositories,
)

from .app import App

cli_app = typer.Typer(
    context_settings={
        "auto_envvar_prefix": "GITHUBTOKENCLIENT",
    }
)


@dataclass
class TyperState:
    persist_to: Path | None
    username: str | None
    password: str | None
    github_base_url: str = "https://github.com"


def _app_from_typer_state(state: TyperState) -> App:
    return App(
        state.persist_to,
        state.username,
        state.password,
        state.github_base_url,
    )


@cli_app.callback()
def typer_callback(
    ctx: typer.Context,
    persist_to: str = typer.Option(
        None,
        "--persist",
        metavar="PATH",
        help="persist browser state to directory (no persistence if not set)",
    ),
    username: str = typer.Option(
        None,
        "--username",
        "-u",
        help="GitHub username (will prompt for it if not given)",
    ),
    password: str = typer.Option(
        None,
        help="GitHub password "
        "(will prompt for it or load it from the keyring if not given); "
        "you should probably NOT set this via the CLI because it "
        "will then be visible in the list of processes; "
        "it's safer to provide it as an env var",
    ),
    github_base_url: str = typer.Option(
        "https://github.com", help="base URL of the GitHub website to use"
    ),
):
    ctx.obj = TyperState(
        Path(persist_to) if persist_to is not None else None,
        username,
        password,
        github_base_url,
    )


@cli_app.command()
def create_fine_grained(
    ctx: typer.Context,
    token_name: str = typer.Argument(..., help="name of the token"),
    repositories: str = typer.Option(
        None,
        "--repositories",
        "-r",
        help="repositories for which the token should apply (comma-separated)",
    ),
    all_repositories: str = typer.Option(
        False,
        "--all-repositories",
        "-a",
        help="let token apply to all repositories "
        "(mutually exclusive with --repositories)",
    ),
    read_permissions: str = typer.Option(
        None,
        "--read-permissions",
        "-R",
        help="operations for which to grant read permissions, "
        "comma-separated (use the possible-fine-grained-permissions command "
        "to get a list of possible values)",
    ),
    write_permissions: str = typer.Option(
        None,
        "--write-permissions",
        "-W",
        help="operations for which to grant read and write permissions, "
        "comma-separated (use the possible-fine-grained-permissions command "
        "to get a list of possible values)",
    ),
    description: str = typer.Option("", help="token description"),
):
    """
    Create a new fine-grained token on GitHub
    """
    if repositories and all_repositories:
        print(
            "--repositories and --all-repositories are mutually exclusive",
            file=stderr,
        )
        raise typer.Exit(1)
    scope = (
        AllRepositories()
        if all_repositories
        else (
            PublicRepositories()
            if repositories is None
            else SelectRepositories(repositories.split(","))
        )
    )
    permissions = {
        **{
            permission_name: PermissionValue.READ
            for permission_name in (
                read_permissions.split(",") if read_permissions else []
            )
        },
        **{
            permission_name: PermissionValue.WRITE
            for permission_name in (
                write_permissions.split(",") if write_permissions else []
            )
        },
    }
    app = _app_from_typer_state(ctx.obj)
    app.create_fine_grained_token(token_name, scope, description, permissions)


@cli_app.command()
def possible_fine_grained_permissions(ctx: typer.Context):
    """
    List fine-grained permissions that can be set when creating a token.
    """
    app = _app_from_typer_state(ctx.obj)
    app.list_possible_fine_grained_permissions()


@cli_app.command()
def list_fine_grained(ctx: typer.Context):
    """
    List fine-grained tokens on GitHub
    """
    app = _app_from_typer_state(ctx.obj)
    app.list_fine_grained_tokens()


@cli_app.command()
def list_classic(ctx: typer.Context):
    """
    List classic tokens on GitHub
    """
    app = _app_from_typer_state(ctx.obj)
    app.list_fine_grained_tokens()


@cli_app.command()
def delete_fine_grained(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="name of token to delete"),
):
    """
    Delete fine-grained token on GitHub
    """
    app = _app_from_typer_state(ctx.obj)
    app.delete_fine_grained_token(name)


def cli_main():
    # it seems that there is no way around setting global state with Python's
    # own logging module, so setting this up is done in the outermost layer
    # here (=> everything inside has no global state mutations)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cli_app()


if __name__ == "__main__":
    cli_main()
