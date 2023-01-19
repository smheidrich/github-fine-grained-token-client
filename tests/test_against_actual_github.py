"""
Tests that run against an actual GitHub instance.
"""
from os import getenv

import pytest

from github_token_client.app import App
from github_token_client.common import SingleProject

# you have to define all of these to run these tests. you should use a dummy
# account and project obviously
github_base_url = getenv(
    "GITHUBTOKENCLIENT_TEST_GITHUB_BASE_URL", "https://github.com"
)
username = getenv("GITHUBTOKENCLIENT_TEST_USERNAME")
password = getenv("GITHUBTOKENCLIENT_TEST_PASSWORD")
project = getenv("GITHUBTOKENCLIENT_TEST_PROJECT")
# set to 0 for non-headless mode
headless = bool(int(getenv("GITHUBTOKENCLIENT_TEST_HEADLESS", "1")))

pytestmark = [
    pytest.mark.skipif(username is None, reason="no username provided"),
    pytest.mark.skipif(password is None, reason="no password provided"),
    pytest.mark.skipif(project is None, reason="no project provided"),
]


def test_create_list_and_delete_token(tee_capsys):
    capsys = tee_capsys  # shortcut
    app = App(headless, None, username, password, github_base_url)
    token_name = "githubtokenclienttest"

    # delete it in case it's left over from an earlier unsuccessful run
    with capsys.disabled():
        app.delete_token(token_name)

    app.create_token(token_name, SingleProject(project))
    captured = capsys.readouterr()
    assert "Created token:" in captured.out
    app.list_tokens()
    captured = capsys.readouterr()
    assert token_name in captured.out
    app.delete_token(token_name)
    captured = capsys.readouterr()
    assert f"deleting token '{token_name}'" in captured.out
