import locale
from collections import ChainMap
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from logging import getLogger
from textwrap import dedent
from uuid import uuid4

import aiohttp
import dateparser
import pytest
from aiohttp.web import Server
from yarl import URL

from github_fine_grained_token_client.async_client import (
    async_github_fine_grained_token_client,
)
from github_fine_grained_token_client.common import (
    FineGrainedTokenBulkInfo,
    FineGrainedTokenCompletePersistentInfo,
    FineGrainedTokenIndividualInfo,
    FineGrainedTokenStandardInfo,
    LoginError,
    PermissionValue,
)
from github_fine_grained_token_client.credentials import GithubCredentials
from tests.utils_for_tests import assert_lhs_fields_match

logger = getLogger(__name__)


@dataclass
class GithubState:
    credentials: GithubCredentials
    fine_grained_tokens: list[FineGrainedTokenStandardInfo]  # TODO more info
    authenticity_tokens: dict[str, str] = field(default_factory=dict)
    "Mapping from URLs to authenticity tokens to post to them"

    def redeem_authenticity_token(self, token: str, url: str) -> bool:
        """
        Validates and redeems an authenticity token for the given URL.
        """
        logger.debug(f"attempting to redeem authenticity token {token!r}")
        try:
            correct_token = self.authenticity_tokens[url]
            if token != correct_token:
                logger.debug(
                    f"incorrect authenticity token for URL {url!r} "
                    f"(given: {token!r}, correct: {correct_token!r})"
                )
                return False
            logger.debug(f"redeemed authenticity token {token!r}")
            return True
        except KeyError:
            logger.debug(
                f"no authenticity token for URL {url!r} "
                f"(given: {token!r}, available: {self.authenticity_tokens})"
            )
            return False

    def new_authenticity_token(self, url: str) -> str:
        """
        Creates and registers a new authenticity token for the given URL.
        """
        token = uuid4().hex
        self.authenticity_tokens[url] = token
        logger.debug(f"created new authenticity token {token!r}")
        return token


@dataclass
class FakeGitHub:
    state: GithubState
    server: Server

    @property
    def base_url(self) -> str:
        return make_base_url(self.server)


def make_base_url(server) -> str:
    # shitty hack: localhost instead of IP to allow cookies
    return (
        str(server.make_url("/")).replace("127.0.0.1", "localhost").rstrip("/")
    )


def make_url(server, path) -> str:
    return "/".join([make_base_url(server), path.lstrip("/")])


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
            FineGrainedTokenCompletePersistentInfo(
                id=123,
                name="existing token",
                last_used_str="never used",
                created=datetime(2022, 3, 3),
                expires=datetime(2023, 3, 3),
                permissions={
                    "contents": PermissionValue.WRITE,
                },
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
        referrer = request.headers.get("Referer", "")
        request_url = str(request.url)
        action_url = make_url(server, "/sessions/sudo")
        return aiohttp.web.Response(
            text=dedent(
                f"""
                <div id="sudo">
                <div>
                <h1>Confirm password</h1>
                <form action="{action_url}" method="post">
                    <input type="hidden" name="authenticity_token"
                        value="{state.new_authenticity_token(action_url)}">
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
                logger.debug("password already confirmed")
                return await func(request)
            data = await request.post()
            action_url = str(request.url)
            if "sudo_password" not in data:
                logger.debug("showing password confirmation dialog")
                input_elem_strs = "\n".join(
                    f'<input type="hidden" name="{k}" value="{v}">'
                    for k, v in ChainMap(
                        {
                            "authenticity_token": state.new_authenticity_token(
                                action_url
                            )
                        },
                        data,
                    ).items()
                )
                logger.debug(f"creating form with: {input_elem_strs!r}")
                referrer = request.headers.get("Referer", "")
                return aiohttp.web.Response(
                    text=dedent(
                        f"""
                        <div id="sudo">
                        <div>
                        <h1>Confirm password</h1>
                        <form action="{action_url}" method="post">
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
            logger.debug("password will be set to confirmed after inner fn")
            response = await func(request)
            response.set_cookie("password-confirmed", "true")
            return response

        return new_func

    def auto_redeem_authenticity_token(func):
        """
        Decorator to automatically check and redeem authenticity tokens.
        """

        @wraps(func)
        async def new_func(request):
            data = await request.post()
            token = data["authenticity_token"]
            request_url = str(request.url)
            if not state.redeem_authenticity_token(token, request_url):
                raise aiohttp.web.HTTPBadRequest(
                    reason="invalid authenticity token"
                )
            return await func(request)

        return new_func

    @routes.get("/login")
    async def login(request):
        if request.cookies.get("logged-in") == "true":
            return aiohttp.web.HTTPFound("/")
        return_to = request.query.get("return_to") or request.url.with_path(
            "/login"
        )
        action_path = "/session"
        action_url = make_url(server, action_path)
        return aiohttp.web.Response(
            text=dedent(
                f"""
                <form action="{action_path}" accept-charset="UTF-8"
                    method="post"
                >
                <input type="hidden" name="authenticity_token"
                    value="{state.new_authenticity_token(action_url)}"
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
    @auto_redeem_authenticity_token
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
    @auto_redeem_authenticity_token
    async def sudo(request):
        data = await request.post()
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
                              action="{action_path}"
                              accept-charset="UTF-8" method="post"
                          >
                              <input type="hidden" name="_method"
                                  value="delete"
                              />
                              <input type="hidden" name="authenticity_token"
                                  value="{authenticity_token}" />
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
                      src="{fragment_url}"
                  >
                    <span>Loading expiration ...</span>
                    <p hidden>Sorry, something went wrong.</p>
                  </include-fragment>
                </div>
              </div>
            </div>
            """
            for token, action_path, authenticity_token, fragment_url in (
                (
                    token,
                    f"/settings/personal-access-tokens/{token.id}",
                    state.new_authenticity_token(
                        make_url(
                            server,
                            f"/settings/personal-access-tokens/{token.id}",
                        )
                    ),
                    f"/settings/personal-access-tokens/{token.id}/expiration"
                    "?page=1",
                )
                for token in state.fine_grained_tokens
            )
        ]
        tokens_html = "\n\n".join(token_htmls)
        page_html = f'<div class="listgroup">{tokens_html}</div>'
        return aiohttp.web.Response(text=page_html)

    @routes.get("/settings/personal-access-tokens/{token_id}/expiration")
    async def fine_grained_token_expiration(request):
        if request.query["page"] != "1":
            return aiohttp.web.HTTPNotFound()
        token_id = int(request.match_info["token_id"])
        token = {token.id: token for token in state.fine_grained_tokens}[
            token_id
        ]
        locale.setlocale(locale.LC_ALL, "C")  # TODO shitty hakc
        expiration_str = token.expires.strftime("%a, %b %d %Y")
        return aiohttp.web.Response(
            text=f"Expires <span>on {expiration_str}</span>"
        )

    @routes.get("/settings/personal-access-tokens/{token_id:[0-9]+}")
    async def fine_grained_token_page(request):
        token_id = int(request.match_info["token_id"])
        for i, token in enumerate(state.fine_grained_tokens):
            if token.id == token_id:
                token = state.fine_grained_tokens[i]
                break
        else:
            return aiohttp.web.HTTPNotFound()
        permissions_html = "\n".join(
            [
                dedent(
                    f"""
                <li>
                    <input type="radio"
                        name="integration[default_permissions][{perm_id}]"
                        value="{poss_value.value}"
                        {"checked" if perm_value == poss_value else ""}
                    >
                </li>
            """
                )
                for perm_id, perm_value in token.permissions.items()
                for poss_value in PermissionValue
            ]
        )
        return aiohttp.web.Response(
            text=dedent(
                f"""
                <h2>
                  <p>{token.name}</p>
                </h2>
                <div class="clearfix mb-1">
                  <p class="float-left">
                    Created on <span>{token.created}</span>
                  </p>
                </div>
                {permissions_html}
                """
            )
        )

    @routes.post("/settings/personal-access-tokens/{token_id}")
    @auto_redeem_authenticity_token
    @embedded_password_confirmation
    async def delete_fine_grained_token(request):
        token_id = int(request.match_info["token_id"])
        data = await request.post()
        if data["_method"] != "delete":
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
    async def create_fine_grained_token_page(request):
        action_url = make_url(server, "/settings/personal-access-tokens")
        return aiohttp.web.Response(
            text=f"""
            <form id="new_user_programmatic_access">
                <input name="authenticity_token"
                    value="{state.new_authenticity_token(action_url)}"
                />
            </form>
            """
        )

    @routes.post("/settings/personal-access-tokens")
    @auto_redeem_authenticity_token
    async def create_fine_grained_token_call(request):
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
    async with async_github_fine_grained_token_client(
        credentials,
        base_url=fake_github.base_url,
    ) as client:
        await client.login()


async def test_login_with_persistence(fake_github, credentials, tmp_path):
    async with async_github_fine_grained_token_client(
        credentials,
        base_url=fake_github.base_url,
        persist_to=tmp_path,
    ) as client:
        assert await client.login()  # had to login => returns True
    async with async_github_fine_grained_token_client(
        credentials,
        base_url=fake_github.base_url,
        persist_to=tmp_path,
    ) as client:
        assert not await client.login()  # no login needed => returns False


async def test_login_wrong_username(fake_github):
    async with async_github_fine_grained_token_client(
        GithubCredentials("wronguser", "wrongpw"),
        base_url=fake_github.base_url,
    ) as client:
        with pytest.raises(LoginError):
            await client.login()


async def test_login_wrong_password(fake_github, credentials):
    async with async_github_fine_grained_token_client(
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
    async with async_github_fine_grained_token_client(
        credentials,
        base_url=fake_github.base_url,
    ) as client:
        tokens = await client.get_tokens_minimal()
        for token, reference_token in zip(
            tokens, fake_github.state.fine_grained_tokens
        ):
            assert isinstance(token, FineGrainedTokenBulkInfo)
            assert_lhs_fields_match(
                token, fake_github.state.fine_grained_tokens[0]
            )


async def test_get_fine_grained_tokens(fake_github, credentials):
    async with async_github_fine_grained_token_client(
        credentials,
        base_url=fake_github.base_url,
    ) as client:
        tokens = await client.get_tokens()
        for token, reference_token in zip(
            tokens, fake_github.state.fine_grained_tokens
        ):
            assert isinstance(token, FineGrainedTokenBulkInfo)
            assert_lhs_fields_match(
                token, fake_github.state.fine_grained_tokens[0]
            )


async def test_get_fine_grained_token_info(fake_github, credentials):
    async with async_github_fine_grained_token_client(
        credentials,
        base_url=fake_github.base_url,
    ) as client:
        token_info = await client.get_token_info(123)
        assert isinstance(token_info, FineGrainedTokenIndividualInfo)
        assert_lhs_fields_match(
            token_info, fake_github.state.fine_grained_tokens[0]
        )


async def test_get_complete_persistent_fine_grained_token_info(
    fake_github, credentials
):
    async with async_github_fine_grained_token_client(
        credentials,
        base_url=fake_github.base_url,
    ) as client:
        token_info = await client.get_complete_persistent_token_info(123)
        assert isinstance(token_info, FineGrainedTokenIndividualInfo)
        assert_lhs_fields_match(
            token_info, fake_github.state.fine_grained_tokens[0]
        )


@pytest.mark.parametrize(
    "fake_github",
    [
        {},
        {"password_confirmation": {"/settings/personal-access-tokens/123"}},
        {"password_confirmation": {"/settings/tokens?type=beta"}},
    ],
    indirect=True,
)
async def test_delete_fine_grained_tokens(fake_github, credentials):
    async with async_github_fine_grained_token_client(
        credentials,
        base_url=fake_github.base_url,
    ) as client:
        await client.delete_token("existing token")
    assert fake_github.state.fine_grained_tokens == []


# TODO test permissions etc. as well => access state directly instead of fetch
@pytest.mark.parametrize(
    "fake_github",
    [{}, {"password_confirmation": {"/settings/personal-access-tokens/new"}}],
    indirect=True,
)
async def test_create_fine_grained_tokens(fake_github, credentials):
    async with async_github_fine_grained_token_client(
        credentials,
        base_url=make_base_url(fake_github.server),
    ) as client:
        name = "new token"
        expires = datetime(2023, 2, 5)
        description = "some description"
        await client.create_token(name, expires, description)
    new_token_info = fake_github.state.fine_grained_tokens[-1]
    assert new_token_info.name == name
    assert new_token_info.expires == expires
