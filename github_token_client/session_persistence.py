from pathlib import Path
from warnings import warn

from aiohttp import CookieJar

from github_token_client.async_client import GithubTokenClientSessionState

cookies_filename = "cookies.pickle"


def save_session_state(
    dir_path: Path,
    state: GithubTokenClientSessionState,
    create_parents: bool = True,
) -> None:
    dir_path.mkdir(exist_ok=True, parents=create_parents)
    # save cookies using provided method (dumb b/c uses pickle but oh well)
    state.cookie_jar.save(dir_path / cookies_filename)


def load_session_state(
    dir_path: Path,
) -> GithubTokenClientSessionState | None:
    cookies_path = dir_path / cookies_filename
    cookie_jar = CookieJar()
    try:
        cookie_jar.load(cookies_path)
    except Exception:
        # TODO add proper logging using logging module instead
        warn(f"error reading pickled cookies at {cookies_path} - ignoring")
        return None
    return GithubTokenClientSessionState(cookie_jar=cookie_jar)
