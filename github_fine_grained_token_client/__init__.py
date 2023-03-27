from importlib import metadata

from .async_client import (
    AsyncGithubFineGrainedTokenClientSession,
    async_github_fine_grained_token_client,
)
from .common import (
    AllRepositories,
    FineGrainedTokenBulkInfo,
    FineGrainedTokenScope,
    FineGrainedTokenStandardInfo,
    LoginError,
    PasswordError,
    PublicRepositories,
    SelectRepositories,
    TooManyAttemptsError,
    UsernameError,
)
from .credentials import GithubCredentials

# TODO: I really hate this as it uses the installed version which isn't
#   necessarily the one being run => put static version here once tool for
#   https://softwarerecs.stackexchange.com/questions/86673 exists
__version__ = metadata.version(__package__)
__distribution_name__ = metadata.metadata(__package__)["Name"]

__all__ = [
    "async_github_fine_grained_token_client",
    "AsyncGithubFineGrainedTokenClientSession",
    "GithubCredentials",
    "LoginError",
    "UsernameError",
    "PasswordError",
    "TooManyAttemptsError",
    "FineGrainedTokenScope",
    "AllRepositories",
    "PublicRepositories",
    "SelectRepositories",
    "FineGrainedTokenBulkInfo",
    "FineGrainedTokenStandardInfo",
]
