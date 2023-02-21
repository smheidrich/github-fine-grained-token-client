from dataclasses import dataclass
from textwrap import dedent

import aiohttp
import pytest
from github_token_client.async_client import async_github_token_client

from github_token_client.common import FineGrainedTokenStandardInfo, LoginError
from github_token_client.credentials import GithubCredentials


@dataclass
class GithubState:
    credentials: GithubCredentials
    fine_grained_tokens: list[FineGrainedTokenStandardInfo]  # TODO more info


@pytest.fixture
async def fake_github(aiohttp_server, credentials):
    state = GithubState(credentials, [])
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

    app = aiohttp.web.Application()
    app.add_routes(routes)
    return await aiohttp_server(app)


@pytest.fixture
def credentials():
    return GithubCredentials(username="testuser", password="testpassword")


async def test_login(fake_github, credentials):
    async with async_github_token_client(
        credentials, base_url=str(fake_github.make_url("/"))
    ) as client:
        await client.login()


async def test_wrong_username(fake_github):
    async with async_github_token_client(
        GithubCredentials("wronguser", "wrongpw"),
        base_url=str(fake_github.make_url("/")),
    ) as client:
        with pytest.raises(LoginError):
            await client.login()


async def test_wrong_password(fake_github, credentials):
    async with async_github_token_client(
        GithubCredentials(credentials.username, "wrongpw"),
        base_url=str(fake_github.make_url("/")),
    ) as client:
        with pytest.raises(LoginError):
            await client.login()
