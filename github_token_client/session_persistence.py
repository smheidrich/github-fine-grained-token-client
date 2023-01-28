import json
from pathlib import Path

from github_token_client.async_client import GithubTokenClientSessionState


class MalformedSessionStateFile(Exception):
    pass


def save_session_state(
    path: Path,
    state: GithubTokenClientSessionState,
    create_parents: bool = True,
) -> None:
    if create_parents:
        path.parent.mkdir(exist_ok=True, parents=True)
    with path.open("w") as f:
        json.dump(
            {"version": "1", "data": {"cookies": dict(state.cookies.jar)}}, f
        )


def load_session_state(
    path: Path,
) -> GithubTokenClientSessionState | None:
    # TODO add logging in case of errors
    try:
        with path.open() as f:
            d = json.load(f)
            version = d["version"]
            if version != "1":
                return None
            return GithubTokenClientSessionState(cookies=d["data"]["cookies"])
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return None
