"""
GitHub credential data structure and utilities.
"""
from dataclasses import dataclass
from getpass import getpass


@dataclass
class GithubCredentials:
    username: str
    "GitHub username"
    password: str
    "GitHub password"


def prompt_for_credentials(username: str | None = None) -> GithubCredentials:
    if username is None:
        username = input("github username: ")
    password = getpass("github password: ")
    return GithubCredentials(username, password)
