from enum import Enum
from typing import TypeAlias, TypeVar, cast

from enum_properties import EnumProperties, p  # type: ignore

try:
    from enum_tools import document_enum
except ImportError:  # enum_tools is only available when doc deps installed

    T = TypeVar("T")

    def document_enum(x: T) -> T:  # type: ignore[misc]
        return x


@document_enum
class PermissionValue(Enum):
    """
    The extent to which a permission applies.
    """

    NONE = ""
    "Not at all"
    READ = "read"
    "Read-only"
    WRITE = "write"
    "Read and write"


class RepositoryPermission(
    EnumProperties, p("full_name"), p("allowed_values")  # type: ignore[misc]
):
    ACTIONS = (
        "actions",
        "Actions",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    ADMINISTRATION = (
        "administration",
        "Administration",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    SECURITY_EVENTS = (
        "security_events",
        "Code scanning alerts",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    CODESPACES = (
        "codespaces",
        "Codespaces",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    CODESPACES_LIFECYCLE_ADMIN = (
        "codespaces_lifecycle_admin",
        "Codespaces lifecycle admin",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    CODESPACES_METADATA = (
        "codespaces_metadata",
        "Codespaces metadata",
        (PermissionValue.NONE, PermissionValue.READ),
    )
    CODESPACES_SECRETS = (
        "codespaces_secrets",
        "Codespaces secrets",
        (PermissionValue.NONE, PermissionValue.WRITE),
    )
    STATUSES = (
        "statuses",
        "Commit statuses",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    CONTENTS = (
        "contents",
        "Contents",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    VULNERABILITY_ALERTS = (
        "vulnerability_alerts",
        "Dependabot alerts",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    DEPENDABOT_SECRETS = (
        "dependabot_secrets",
        "Dependabot secrets",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    DEPLOYMENTS = (
        "deployments",
        "Deployments",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    DISCUSSIONS = (
        "discussions",
        "Discussions",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    ENVIRONMENTS = (
        "environments",
        "Environments",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    ISSUES = (
        "issues",
        "Issues",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    MERGE_QUEUES = (
        "merge_queues",
        "Merge queues",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    METADATA = (
        "metadata",
        "Metadata",
        (PermissionValue.NONE, PermissionValue.READ),
    )
    PAGES = (
        "pages",
        "Pages",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    PULL_REQUESTS = (
        "pull_requests",
        "Pull requests",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    REPOSITORY_ADVISORIES = (
        "repository_advisories",
        "Repository security advisories",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    SECRET_SCANNING_ALERTS = (
        "secret_scanning_alerts",
        "Secret scanning alerts",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    SECRETS = (
        "secrets",
        "Secrets",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    ACTIONS_VARIABLES = (
        "actions_variables",
        "Variables",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    REPOSITORY_HOOKS = (
        "repository_hooks",
        "Webhooks",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    WORKFLOWS = (
        "workflows",
        "Workflows",
        (PermissionValue.NONE, PermissionValue.WRITE),
    )


class AccountPermission(
    EnumProperties, p("full_name"), p("allowed_values")  # type: ignore[misc]
):
    BLOCKING = (
        "blocking",
        "Block another user",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    CODESPACES_USER_SECRETS = (
        "codespaces_user_secrets",
        "Codespaces user secrets",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    EMAILS = (
        "emails",
        "Email addresses",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    FOLLOWERS = (
        "followers",
        "Followers",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    GPG_KEYS = (
        "gpg_keys",
        "GPG keys",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    GISTS = "gists", "Gists", (PermissionValue.NONE, PermissionValue.WRITE)
    KEYS = (
        "keys",
        "Git SSH keys",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    INTERACTION_LIMITS = (
        "interaction_limits",
        "Interaction limits",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    PLAN = "plan", "Plan", (PermissionValue.NONE, PermissionValue.READ)
    PRIVATE_REPOSITORY_INVITATIONS = (
        "private_repository_invitations",
        "Private repository invitations",
        (PermissionValue.NONE, PermissionValue.READ),
    )
    PROFILE = (
        "profile",
        "Profile",
        (PermissionValue.NONE, PermissionValue.WRITE),
    )
    GIT_SIGNING_SSH_PUBLIC_KEYS = (
        "git_signing_ssh_public_keys",
        "SSH signing keys",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    STARRING = (
        "starring",
        "Starring",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )
    WATCHING = (
        "watching",
        "Watching",
        (PermissionValue.NONE, PermissionValue.READ, PermissionValue.WRITE),
    )


AnyPermissionKey: TypeAlias = AccountPermission | RepositoryPermission

ALL_PERMISSION_KEYS = list(AccountPermission) + list(RepositoryPermission)


def permission_from_str(permission_str: str) -> AnyPermissionKey:
    for enum_class in [AccountPermission, RepositoryPermission]:
        try:
            return cast(AnyPermissionKey, enum_class(permission_str))
        except ValueError:
            pass
    raise KeyError(f"no permission found for string {permission_str!r}")
