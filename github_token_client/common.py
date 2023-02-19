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


class TokenCreationError(Exception):
    pass


class TokenNameError(TokenCreationError):
    pass


class TokenNameAlreadyTakenError(TokenNameError):
    pass


class RepositoryNotFoundError(Exception):
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
    "Repository names"


@dataclass
class FineGrainedTokenMinimalInfo:
    """
    Information on a fine-grained token obtainable with just one bulk request.
    """

    id: int
    name: str
    # last_used: datetime | None  # TODO
    last_used_str: str


@dataclass
class FineGrainedTokenStandardInfo(FineGrainedTokenMinimalInfo):
    """
    Information on a fine-grained token as shown in the list on the website.
    """

    expires: datetime


@dataclass
class ClassicTokenMinimalInfo:
    """
    Information on a classic token obtainable with just one bulk request.
    """

    id: int
    name: str
    expires: datetime | None
    # last_used: datetime | None  # TODO
    last_used_str: str


@dataclass
class ClassicTokenStandardInfo(ClassicTokenMinimalInfo):
    """
    Information on a classic token as shown in the list on the website.
    """

    pass
