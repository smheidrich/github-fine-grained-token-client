"""
Data structures common to both sync and async client.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
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


class PermissionValue(Enum):
    NONE = ""
    READ = "read"
    WRITE = "write"


@dataclass
class FineGrainedTokenMinimalInfo:
    """
    Absolutely minimal information on a token.
    """

    id: int
    name: str


@dataclass
class FineGrainedTokenBulkInfo:
    """
    Information on a fine-grained token obtainable with just one bulk request.
    """

    id: int
    name: str
    # last_used: datetime | None  # TODO
    last_used_str: str


@dataclass
class FineGrainedTokenStandardInfo(FineGrainedTokenBulkInfo):
    """
    Information on a fine-grained token as shown in the list on the website.
    """

    expires: datetime


@dataclass
class FineGrainedTokenIndividualInfo(FineGrainedTokenMinimalInfo):
    """
    Information on a fine-grained token as shown on the token's own page.

    Contains almost everything except the last used date for some reason.
    """

    created: datetime
    expires: datetime
    permissions: Mapping[str, PermissionValue]
