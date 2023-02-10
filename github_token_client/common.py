"""
Data structures common to both sync and async client.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

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
class FineGrainedTokenScope:
    pass


@dataclass
class PublicRepositories(FineGrainedTokenScope):
    pass


@dataclass
class AllRepositories(FineGrainedTokenScope):
    pass


@dataclass
class SelectRepositories(FineGrainedTokenScope):
    names: Sequence[str]
    "Fully-qualified project names (i.e. ``user/project``)"


@dataclass
class FineGrainedTokenBasics:
    id: int
    name: str


@dataclass
class FineGrainedTokenSummary(FineGrainedTokenBasics):
    # last_used: datetime | None  # TODO
    last_used_str: str


@dataclass
class FineGrainedTokenDetails(FineGrainedTokenSummary):
    expires: datetime


@dataclass
class ClassicTokenBasics:
    id: int
    name: str


@dataclass
class ClassicTokenSummary(ClassicTokenBasics):
    expires: datetime | None
    # last_used: datetime | None  # TODO
    last_used_str: str


@dataclass
class ClassicTokenDetails(ClassicTokenSummary):
    pass
