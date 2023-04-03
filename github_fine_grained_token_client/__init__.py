from importlib import metadata

from .asynchronous_client import AsyncClientSession, async_client
from .common import (
    AllRepositories,
    FineGrainedTokenBulkInfo,
    FineGrainedTokenCompletePersistentInfo,
    FineGrainedTokenIndividualInfo,
    FineGrainedTokenMinimalInfo,
    FineGrainedTokenScope,
    FineGrainedTokenStandardInfo,
    LoginError,
    PasswordError,
    PublicRepositories,
    RepositoryNotFoundError,
    SelectRepositories,
    TokenCreationError,
    TokenNameAlreadyTakenError,
    TokenNameError,
    TooManyAttemptsError,
    TwoFactorAuthenticationError,
    UsernameError,
)
from .credentials import GithubCredentials
from .permissions import (
    AccountPermission,
    AnyPermissionKey,
    PermissionValue,
    RepositoryPermission,
)
from .two_factor_authentication import (
    BlockingPromptTwoFactorOtpProvider,
    NullTwoFactorOtpProvider,
    ThreadedPromptTwoFactorOtpProvider,
    TwoFactorOtpProvider,
)

# TODO: I really hate this as it uses the installed version which isn't
#   necessarily the one being run => put static version here once tool for
#   https://softwarerecs.stackexchange.com/questions/86673 exists
__version__ = metadata.version(__package__)
__distribution_name__ = metadata.metadata(__package__)["Name"]

__all__ = [
    # client
    "async_client",
    "AsyncClientSession",
    # credentials
    "GithubCredentials",
    # exceptions
    "LoginError",
    "UsernameError",
    "PasswordError",
    "TooManyAttemptsError",
    "TwoFactorAuthenticationError",
    "TokenCreationError",
    "TokenNameError",
    "TokenNameAlreadyTakenError",
    "RepositoryNotFoundError",
    # scopes
    "FineGrainedTokenScope",
    "AllRepositories",
    "PublicRepositories",
    "SelectRepositories",
    # token info
    "FineGrainedTokenMinimalInfo",
    "FineGrainedTokenBulkInfo",
    "FineGrainedTokenStandardInfo",
    "FineGrainedTokenIndividualInfo",
    "FineGrainedTokenCompletePersistentInfo",
    # permissions
    "AccountPermission",
    "AnyPermissionKey",
    "PermissionValue",
    "RepositoryPermission",
    # 2fa otp providers
    "TwoFactorOtpProvider",
    "NullTwoFactorOtpProvider",
    "BlockingPromptTwoFactorOtpProvider",
    "ThreadedPromptTwoFactorOtpProvider",
]
