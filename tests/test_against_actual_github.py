"""
Tests that run against an actual GitHub instance.
"""
from contextlib import suppress
from os import getenv

import pytest

from github_fine_grained_token_client.app import App
from github_fine_grained_token_client.common import SelectRepositories

# you have to define all of these to run these tests. you should use a dummy
# account and project obviously
github_base_url = getenv(
    "GITHUBFINEGRAINEDTOKENCLIENT_TEST_GITHUB_BASE_URL", "https://github.com"
)
username = getenv("GITHUBFINEGRAINEDTOKENCLIENT_TEST_USERNAME")
password = getenv("GITHUBFINEGRAINEDTOKENCLIENT_TEST_PASSWORD")
project = getenv("GITHUBFINEGRAINEDTOKENCLIENT_TEST_PROJECT")

pytestmark = [
    pytest.mark.skipif(username is None, reason="no username provided"),
    pytest.mark.skipif(password is None, reason="no password provided"),
    pytest.mark.skipif(project is None, reason="no project provided"),
]


# TODO testing the app should really be done via unit tests using the fake
#   github API and the sequence below should be done via the client directly
#   so it's easy to get the ID etc.
def test_app_create_list_show_and_delete_token(tee_capsys):
    capsys = tee_capsys  # shortcut
    app = App(None, username, password, github_base_url)
    token_name = "githubfinegrainedtokenclienttest"

    # delete it in case it's left over from an earlier unsuccessful run
    with capsys.disabled(), suppress(KeyError):
        app.delete_token(token_name)

    app.create_token(token_name, SelectRepositories([project]))
    captured = capsys.readouterr()
    assert "Created token:" in captured.out
    app.list_tokens()
    captured = capsys.readouterr()
    assert token_name in captured.out
    app.show_token_info_by_name(token_name, complete=True)
    captured = capsys.readouterr()
    assert token_name in captured.out
    did_delete = app.delete_token(token_name)
    assert did_delete
    captured = capsys.readouterr()
    assert f"Deleted token '{token_name}'" in captured.out
