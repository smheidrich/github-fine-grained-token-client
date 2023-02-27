import locale
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from textwrap import dedent

import aiohttp
import dateparser
import pytest
from aiohttp.web import Server
from yarl import URL

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

    @property
    def base_url(self) -> str:
        return make_base_url(self.server)


def make_base_url(server) -> str:
    # shitty hack: localhost instead of IP to allow cookies
    return str(server.make_url("/")).replace("127.0.0.1", "localhost")


@pytest.fixture
async def fake_github(aiohttp_server, credentials, request):
    # don't get confused: the above request param is a special pytest fixture,
    # while the ones in the functions below are standard aiohttp params
    password_confirmation_required_for = getattr(request, "param", {}).get(
        "password_confirmation", set()
    )
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
    server: aiohttp.test_utils.BaseServer | None = None

    def login_redirect_if_not_logged_in(request):
        if request.cookies.get("logged-in") == "true":
            return None
        return aiohttp.web.HTTPFound(
            URL("/login").with_query(return_to=str(request.url))
        )

    def auto_login_redirect_if_not_logged_in(func):
        """
        Decorator to use the above automatically.
        """

        @wraps(func)
        async def new_func(request):
            if redirect := login_redirect_if_not_logged_in(request):
                return redirect
            return await func(request)

        return new_func

    def password_confirmation_prompt_if_not_confirmed(
        request,
    ) -> aiohttp.web.Response | None:
        if request.cookies.get("password-confirmed") == "true":
            return None
        base_url = make_base_url(server).rstrip("/")
        referrer = request.headers.get("Referer", "")
        request_url = str(request.url)
        return aiohttp.web.Response(
            text=dedent(
                f"""
                <div id="sudo">
                <div>
                <h1>Confirm password</h1>
                <form action="{base_url}/sessions/sudo" method="post">
                    <input type="hidden" name="authenticity_token"
                        value="confirm-pw-authenticity-token">
                    <input type="hidden" name="sudo_referrer"
                        value="{referrer}">
                    <input type="hidden" name="sudo_return_to"
                        value="{request_url}">
                    <input type="hidden" name="credential_type"
                        value="password">
                    <input type="password" name="sudo_password">
                </form>
                </div>
                </div>
                """
            )
        )

    def dedicated_password_confirmation(func):
        """
        Decorator for endpoints that let the sudo endpoint check the password.

        Will only redirect if the password hasn't been confirmed yet.

        The sudo endpoint redirects to the original target page if the password
        was correct. This kind of password confirmation is only used for GET
        requests, otherwise the redirect makes no sense.
        """

        @wraps(func)
        async def new_func(request):
            if (
                request.url.path in password_confirmation_required_for
                and (
                    response := password_confirmation_prompt_if_not_confirmed(
                        request
                    )
                )
                is not None
            ):
                return response
            return await func(request)

        return new_func

    def embedded_password_confirmation(func):
        """
        Decorator for endpoints that themselves accept password confirm data.

        Unlike the sudo endpoint, these will also perform their actual action
        after the password has been confirmed, without a redirect. They work a
        bit differently because they have to forward the data sent with the
        original request and are only used for POST endpoints.
        """
        # TODO refactor: extract parts shared with
        # dedicated_password_confirmation,
        # password_confirmation_prompt_if_not_confirmed and the sudo endpoint

        @wraps(func)
        async def new_func(request):
            if request.cookies.get("password-confirmed") == "true":
                return await func(request)
            data = await request.post()
            url = str(request.url)
            if "sudo_password" not in data:
                input_elem_strs = "\n".join(
                    f'<input type="hidden" name="{k}" value="{v}">'
                    for k, v in data.items()
                )
                referrer = request.headers.get("Referer", "")
                return aiohttp.web.Response(
                    text=dedent(
                        f"""
                        <div id="sudo">
                        <div>
                        <h1>Confirm password</h1>
                        <form action="{url}" method="post">
                            {input_elem_strs}
                            <input type="hidden" name="sudo_referrer"
                                value="{referrer}">
                            <input type="hidden" name="credential_type"
                                value="password">
                            <input type="password" name="sudo_password">
                        </form>
                        </div>
                        </div>
                        """
                    )
                )
            # TODO in reality, the authenticity token is different for each
            # step, but not sure how to simulate that easily...
            # if data["authenticity_token"] != "confirm-pw-authenticity-token":
            # return aiohttp.web.BadRequest("incorrect authenticity token")
            if data["sudo_password"] != credentials.password:
                return aiohttp.web.Response(
                    text=dedent(
                        """
                        <div id="js-flash-container">
                            Incorrect username or password.
                        </div>
                        """
                    )
                )
            response = await func(request)
            response.set_cookie("password-confirmed", "true")
            return response

        return new_func

    @routes.get("/login")
    async def login(request):
        if request.cookies.get("logged-in") == "true":
            return aiohttp.web.HTTPFound("/")
        return_to = request.query.get("return_to") or request.url.with_path(
            "/login"
        )
        return aiohttp.web.Response(
            text=dedent(
                f"""
                <form action="/session" accept-charset="UTF-8" method="post">
                <input type="hidden" name="authenticity_token"
                    value="authenticity-token"
                />
                <input type="text" name="login"/>
                <input type="password" name="password" />
                <input type="hidden" name="return_to"
                    value="{return_to}"
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
        data = await request.post()
        destination = data.get("return_to")
        response = aiohttp.web.HTTPFound(str(destination or "/"))
        response.set_cookie("logged-in", "true")
        return response

    @routes.post("/sessions/sudo")
    async def sudo(request):
        data = await request.post()
        if data["authenticity_token"] != "confirm-pw-authenticity-token":
            return aiohttp.web.BadRequest("incorrect authenticity token")
        if data["sudo_password"] != credentials.password:
            return aiohttp.web.Response(
                text=dedent(
                    """
                    <div id="js-flash-container">
                        Incorrect username or password.
                    </div>
                    """
                )
            )
        response = aiohttp.web.HTTPFound(data["sudo_return_to"])
        response.set_cookie("password-confirmed", "true")
        return response

    @routes.get("/")
    async def home(request):
        return aiohttp.web.Response(text="welcome to github")

    @routes.get("/settings/tokens")
    @auto_login_redirect_if_not_logged_in
    @dedicated_password_confirmation
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
    @embedded_password_confirmation
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

    @routes.get("/settings/personal-access-tokens/new")
    @auto_login_redirect_if_not_logged_in
    @dedicated_password_confirmation
    async def create_token_page(request):
        return aiohttp.web.Response(
            text="""
            <form id="new_user_programmatic_access">
                <input name="authenticity_token"
                    value="new-token-authenticity-token"
                />
            </form>
            """
        )

    @routes.post("/settings/personal-access-tokens")
    async def create_token_call(request):
        data = await request.post()
        # TODO also validate other data
        state.fine_grained_tokens.append(
            FineGrainedTokenStandardInfo(
                max(t.id for t in state.fine_grained_tokens) + 1,
                data["user_programmatic_access[name]"],
                "Never used",
                dateparser.parse(
                    data["user_programmatic_access[custom_expires_at]"]
                ),
            )
        )
        return aiohttp.web.Response(
            text='<span id="new-access-token" value="new-token-value"></span>'
        )

    app = aiohttp.web.Application()
    app.add_routes(routes)
    server = await aiohttp_server(app)
    return FakeGitHub(state, server)


@pytest.fixture
def credentials():
    return GithubCredentials(username="testuser", password="testpassword")


async def test_login(fake_github, credentials):
    async with async_github_token_client(
        credentials,
        base_url=fake_github.base_url,
    ) as client:
        await client.login()


async def test_wrong_username(fake_github):
    async with async_github_token_client(
        GithubCredentials("wronguser", "wrongpw"),
        base_url=fake_github.base_url,
    ) as client:
        with pytest.raises(LoginError):
            await client.login()


async def test_wrong_password(fake_github, credentials):
    async with async_github_token_client(
        GithubCredentials(credentials.username, "wrongpw"),
        base_url=fake_github.base_url,
    ) as client:
        with pytest.raises(LoginError):
            await client.login()


@pytest.mark.parametrize(
    "fake_github",
    [{}, {"password_confirmation": {"/settings/tokens"}}],
    indirect=True,
)
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
        base_url=fake_github.base_url,
    ) as client:
        tokens = await client.get_fine_grained_tokens_minimal()
        assert tokens == fake_github.state.fine_grained_tokens


async def test_get_fine_grained_tokens(fake_github, credentials):
    async with async_github_token_client(
        credentials,
        base_url=fake_github.base_url,
    ) as client:
        tokens = await client.get_fine_grained_tokens()
        assert tokens == fake_github.state.fine_grained_tokens


@pytest.mark.parametrize(
    "fake_github",
    [{}, {"password_confirmation": {"/settings/personal-access-tokens/123"}}],
    indirect=True,
)
async def test_delete_fine_grained_tokens(fake_github, credentials):
    async with async_github_token_client(
        credentials,
        base_url=fake_github.base_url,
    ) as client:
        await client.delete_fine_grained_token("existing token")
    assert fake_github.state.fine_grained_tokens == []


# TODO test permissions etc. as well => access state directly instead of fetch
@pytest.mark.parametrize(
    "fake_github",
    [{}, {"password_confirmation": {"/settings/personal-access-tokens/new"}}],
    indirect=True,
)
async def test_create_fine_grained_tokens(fake_github, credentials):
    async with async_github_token_client(
        credentials,
        base_url=make_base_url(fake_github.server),
    ) as client:
        name = "new token"
        expires = datetime(2023, 2, 5)
        description = "some description"
        await client.create_fine_grained_token(name, expires, description)
    new_token_info = fake_github.state.fine_grained_tokens[-1]
    assert new_token_info.name == name
    assert new_token_info.expires == expires
