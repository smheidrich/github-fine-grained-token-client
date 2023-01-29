from dataclasses import dataclass, field

from aiohttp.abc import AbstractCookieJar


@dataclass
class GithubTokenClientSessionState:
    """
    Session state that can be used to preserve logged-in states.

    Re-initializing client session with this and not just credentials can
    reduce the number of unnecessary logins that need to be performed.
    """

    cookie_jar: AbstractCookieJar | None = field(default_factory=None)
