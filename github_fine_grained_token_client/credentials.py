"""
GitHub credential data structure and utilities.
"""
from dataclasses import dataclass
from getpass import getpass

import keyring

keyring_service_prefix = "github-fine-grained-token-client-cli"


@dataclass
class GithubCredentials:
    username: str
    "GitHub username"
    password: str
    "GitHub password"


def make_keyring_service_name(github_base_url: str) -> str:
    return f"{keyring_service_prefix} ({github_base_url})"


def get_credentials_from_keyring_and_prompt(
    github_base_url: str,
    username: str | None = None,
    password: str | None = None,
) -> tuple[GithubCredentials, bool]:
    """
    Get GitHub credentials from both the keyring and by prompting the user.

    Returns:
      Tuple of the credentials and whether the credentials were not in the
      keyring ("credentials are new" boolean).
    """
    if username is not None and password is not None:
        return (GithubCredentials(username, password), False)
    if username is None:
        username = input("github username: ")
    if password is not None:
        return (GithubCredentials(username, password), True)
    credentials = get_credentials_from_keyring(github_base_url, username)
    if credentials is None:
        password = getpass("github password: ")
        return (GithubCredentials(username, password), True)
    return (credentials, False)


def prompt_for_credentials(username: str | None = None) -> GithubCredentials:
    if username is None:
        username = input("github username: ")
    password = getpass("github password: ")
    return GithubCredentials(username, password)


def get_credentials_from_keyring(
    github_base_url: str, username: str
) -> GithubCredentials | None:
    cred = keyring.get_credential(
        make_keyring_service_name(github_base_url), username
    )
    if cred:
        return GithubCredentials(cred.username, cred.password)
    return None


def save_credentials_to_keyring(
    github_base_url: str, credentials: GithubCredentials
):
    keyring.set_password(
        make_keyring_service_name(github_base_url),
        credentials.username,
        credentials.password,
    )
