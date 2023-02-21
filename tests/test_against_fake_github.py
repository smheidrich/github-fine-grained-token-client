import locale
from dataclasses import dataclass
from datetime import datetime
from textwrap import dedent

import aiohttp
import pytest
from aiohttp.web import Server

from github_token_client.async_client import async_github_token_client
from github_token_client.common import (
    FineGrainedTokenMinimalInfo,
    FineGrainedTokenStandardInfo,
    LoginError,
)
from github_token_client.credentials import GithubCredentials


@dataclass
class GithubState:
    credentials: GithubCredentials
    fine_grained_tokens: list[FineGrainedTokenStandardInfo]  # TODO more info


@dataclass
class FakeGitHub:
    state: GithubState
    server: Server


@pytest.fixture
async def fake_github(aiohttp_server, credentials):
    state = GithubState(
        credentials,
        [
            FineGrainedTokenStandardInfo(
                id=123,
                name="existing token",
                last_used_str="never used",
                expires=datetime(2023, 3, 3),
            )
        ],
    )
    routes = aiohttp.web.RouteTableDef()

    @routes.get("/login")
    async def login(request):
        return aiohttp.web.Response(
            text=dedent(
                """
                <form action="/session" accept-charset="UTF-8" method="post">
                <input type="hidden" name="authenticity_token"
                    value="authenticity-token"
                />
                <input type="text" name="login"/>
                <input type="password" name="password" />
                <input type="hidden" name="return_to"
                    value="https://github.com/login"
                />
                </form>
                """
            )
        )

    @routes.post("/session")
    async def session(request):
        data = await request.post()
        if (
            data["login"] != credentials.username
            or data["password"] != credentials.password
        ):
            return aiohttp.web.Response(
                text=dedent(
                    """
                    <div id="js-flash-container" data-turbo-replace="">
                        <div>
                            <div aria-atomic="true" role="alert"
                                class="js-flash-alert"
                            >
                                Incorrect username or password.
                            &nbsp;
                            </div>
                        </div>
                    </div>
                    """
                )
            )
        response = aiohttp.web.HTTPFound("/")
        response.set_cookie("logged-in", "true")
        return response

    @routes.get("/settings/tokens")
    async def fine_grained_tokens(request):
        if request.query["type"] != "beta":
            return aiohttp.web.HTTPNotFound()
        token_htmls = [
            f"""
            <div id="access-token-{token.id}"
                class="access-token" data-id="{token.id}"
                data-type="token"
            >
              <div class="listgroup-item">
                <div class="d-flex float-right">
                  <details>
                      <summary>Delete</summary>
                      <details-dialog aria-label="Confirm token deletion">
                          <div class="Box-footer">
                          </option></form><!-- no idea what this is for -->
                          <form
                              action="/settings/personal-access-tokens/446727"
                              accept-charset="UTF-8" method="post"
                          >
                              <input type="hidden" name="_method"
                                  value="delete"
                              />
                              <input type="hidden" name="authenticity_token"
                                  value="authenticity-token-del-{token.id}" />
                          </form>
                          </div>
                      </details-dialog>
                  </details>
                </div>

                <small class="last-used float-right">
                    {token.last_used_str}
                </small>
                <div class="token-description">
                    <strong class="f5">
                        <a href="/settings/personal-access-tokens/{token.id}">
                            {token.name}
                        </a>
                    </strong>
                </div>
                <div>
                  <include-fragment
                      src="/settings/personal-access-tokens/{token.id}/expiration?page=1"
                  >
                    <span>Loading expiration ...</span>
                    <p hidden>Sorry, something went wrong.</p>
                  </include-fragment>
                </div>
              </div>
            </div>
            """
            for token in state.fine_grained_tokens
        ]
        tokens_html = "\n\n".join(token_htmls)
        page_html = f'<div class="listgroup">{tokens_html}</div>'
        return aiohttp.web.Response(text=page_html)

    @routes.get("/settings/personal-access-tokens/{token_id}/expiration")
    async def expiration(request):
        if request.query["page"] != "1":
            return aiohttp.web.HTTPNotFound()
        token_id = int(request.match_info["token_id"])
        token = {token.id: token for token in state.fine_grained_tokens}[
            token_id
        ]
        locale.setlocale(locale.LC_ALL, "C")
        expiration_str = token.expires.strftime("%a, %b %d %Y")
        return aiohttp.web.Response(
            text=f"Expires <span>on {expiration_str}</span>"
        )

    @routes.post("/settings/personal-access-tokens/{token_id}")
    async def delete(request):
        token_id = int(request.match_info["token_id"])
        data = await request.post()
        if (
            data["_method"] != "delete"
            or data["authenticity_token"]
            != f"authenticity-token-del-{token_id}"
        ):
            # real response is "your browser did sth weird" but anyway...
            return aiohttp.web.HTTPNotFound()
        for i, token in enumerate(state.fine_grained_tokens):
            if token.id == token_id:
                del state.fine_grained_tokens[i]
                break
        else:
            return aiohttp.web.HTTPNotFound()
        return aiohttp.web.Response(
            text='<div role="alert">Deleted personal access token</div>'
        )

    app = aiohttp.web.Application()
    app.add_routes(routes)
    return FakeGitHub(state, await aiohttp_server(app))


@pytest.fixture
def credentials():
    return GithubCredentials(username="testuser", password="testpassword")


async def test_login(fake_github, credentials):
    async with async_github_token_client(
        credentials, base_url=str(fake_github.server.make_url("/"))
    ) as client:
        await client.login()


async def test_wrong_username(fake_github):
    async with async_github_token_client(
        GithubCredentials("wronguser", "wrongpw"),
        base_url=str(fake_github.server.make_url("/")),
    ) as client:
        with pytest.raises(LoginError):
            await client.login()


async def test_wrong_password(fake_github, credentials):
    async with async_github_token_client(
        GithubCredentials(credentials.username, "wrongpw"),
        base_url=str(fake_github.server.make_url("/")),
    ) as client:
        with pytest.raises(LoginError):
            await client.login()


async def test_get_fine_grained_tokens_minimal(fake_github, credentials):
    # TODO this is not correct from type perspective => better minimize result
    fake_github.state.fine_grained_tokens = [
        FineGrainedTokenMinimalInfo(
            id=123,
            name="existing token",
            last_used_str="never used",
        )
    ]
    async with async_github_token_client(
        credentials,
        base_url=str(fake_github.server.make_url("/")),
    ) as client:
        tokens = await client.get_fine_grained_tokens_minimal()
        assert tokens == fake_github.state.fine_grained_tokens


async def test_get_fine_grained_tokens(fake_github, credentials):
    async with async_github_token_client(
        credentials,
        base_url=str(fake_github.server.make_url("/")),
    ) as client:
        tokens = await client.get_fine_grained_tokens()
        assert tokens == fake_github.state.fine_grained_tokens


async def test_delete_fine_grained_tokens(fake_github, credentials):
    async with async_github_token_client(
        credentials,
        base_url=str(fake_github.server.make_url("/")),
    ) as client:
        await client.delete_fine_grained_token("existing token")
        tokens = await client.get_fine_grained_tokens()
        assert tokens == []
