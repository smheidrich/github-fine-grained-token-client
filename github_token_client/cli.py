import logging
from dataclasses import dataclass
from pathlib import Path

import typer

from github_token_client.common import AllRepositories, SelectRepositories

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
    project: str = typer.Option(
        None, help="project for which to generate token"
    ),
    description: str = typer.Option("", help="token description"),
):
    """
    Create a new fine-grained token on GitHub
    """
    scope = (
        AllRepositories() if project is None else SelectRepositories([project])
    )
    app = _app_from_typer_state(ctx.obj)
    app.create_token(token_name, scope, description)


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
