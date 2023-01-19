"""
Data structures common to both sync and async client.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

user_data_dir = str(Path("~/.autogithubtok/persist-chromium").expanduser())
max_login_attempts = 3


class UnexpectedPageError(Exception):
    pass


class UnexpectedContentError(Exception):
    pass


class LoginError(Exception):
    pass


class UsernameError(LoginError):
    pass


class PasswordError(LoginError):
    pass


class TooManyAttemptsError(LoginError):
    pass


class TokenNameError(Exception):
    pass


@dataclass
class TokenScope:
    pass


@dataclass
class AllProjects(TokenScope):
    pass


@dataclass
class SingleProject(TokenScope):
    name: str
    "Name of the project for which this token should be valid"


@dataclass
class TokenListEntry:
    name: str
    scope: TokenScope
    created: datetime
    last_used: datetime | None
