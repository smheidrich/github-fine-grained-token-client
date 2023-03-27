import logging
from dataclasses import dataclass
from pathlib import Path
from sys import stderr

import typer

from .app import App
from .async_client import PermissionValue
from .common import AllRepositories, PublicRepositories, SelectRepositories
from .permissions import permission_from_str

cli_app = typer.Typer(
    context_settings={
        "auto_envvar_prefix": "GITHUBFINEGRAINEDTOKENCLIENT",
    }
)


@dataclass
class TyperState:
    persist_to: Path | None
    username: str | None
    password: str | None
    github_base_url: str = "https://github.com"
    verbosity: int = logging.WARNING


def _app_from_typer_state(state: TyperState) -> App:
    # it seems that there is no way around setting global state with Python's
    # own logging module, so setting this up is done in the outermost layer
    # here (=> everything inside has no global state mutations)
    logging.basicConfig(level=state.verbosity)
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
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="verbose output (repeat to increases verbosity, e.g. -vv, -vvv)",
    ),
):
    ctx.obj = TyperState(
        Path(persist_to) if persist_to is not None else None,
        username,
        password,
        github_base_url,
        verbosity={
            0: logging.WARNING,
            1: logging.INFO,
            2: logging.DEBUG,
            3: logging.NOTSET,
        }.get(verbose, 3),
    )


@cli_app.command()
def create(
    ctx: typer.Context,
    token_name: str = typer.Argument(..., help="name of the token"),
    repositories: str = typer.Option(
        None,
        "--repositories",
        "-r",
        help="repositories for which the token should apply (comma-separated)",
    ),
    all_repositories: bool = typer.Option(
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
        help="operations for which to grant read *and* write permissions, "
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
            permission_from_str(permission_name): PermissionValue.READ
            for permission_name in (
                read_permissions.split(",") if read_permissions else []
            )
        },
        **{
            permission_from_str(permission_name): PermissionValue.WRITE
            for permission_name in (
                write_permissions.split(",") if write_permissions else []
            )
        },
    }
    app = _app_from_typer_state(ctx.obj)
    app.create_token(token_name, scope, description, permissions)


@cli_app.command()
def possible_permissions(
    ctx: typer.Context,
    fetch: bool = typer.Option(
        False, help="fetch possible permissions from GitHub website"
    ),
    codegen: bool = typer.Option(
        False, help="output as enum code (for dev use); requires --fetch"
    ),
):
    """
    List fine-grained permissions that can be set when creating a token.
    """
    if codegen and not fetch:
        print("--codegen requires --fetch", file=stderr)
        raise typer.Exit(1)
    app = _app_from_typer_state(ctx.obj)
    app.list_fetched_possible_permissions(fetch, codegen)


@cli_app.command("list")
def list_tokens(ctx: typer.Context):
    """
    List fine-grained tokens on GitHub
    """
    app = _app_from_typer_state(ctx.obj)
    app.list_tokens()


@cli_app.command()
def info(
    ctx: typer.Context,
    name_or_id: str = typer.Argument(
        ...,
        help="name or ID of token, "
        "decided based on whether it's a number or not; "
        "see --name and --id for forcing one or the other",
    ),
    name: bool = typer.Option(
        False, help="force interpreting NAME_OR_ID as a name"
    ),
    id: bool = typer.Option(
        False, help="force interpreting NAME_OR_ID as an ID"
    ),
    complete: bool = typer.Option(
        False,
        help="fetch information not on the token's own page "
        "(specifically, the last-used date)",
    ),
):
    """
    Print information about a fine-grained token
    """
    app = _app_from_typer_state(ctx.obj)
    if name and id:
        print(
            "--name and --id are mutually exclusive",
            file=stderr,
        )
        raise typer.Exit(1)
    if id or (name_or_id.isdigit() and not name):
        app.show_token_info_by_id(int(name_or_id), complete)
    else:
        app.show_token_info_by_name(name_or_id, complete)


@cli_app.command()
def delete(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="name of token to delete"),
    exit_code: bool = typer.Option(
        False,
        help="return a non-zero exit code if the token doesn't exist",
    ),
):
    """
    Delete fine-grained token on GitHub
    """
    app = _app_from_typer_state(ctx.obj)
    did_delete = app.delete_token(name)
    if exit_code and not did_delete:
        raise typer.Exit(2)


def cli_main():
    cli_app()


if __name__ == "__main__":
    cli_main()
