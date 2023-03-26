from contextlib import contextmanager
from functools import wraps
from logging import Logger, getLogger
from pathlib import Path
from traceback import print_exc
from typing import Type, TypeVar
from warnings import warn

import aiohttp

from .abstract_http_session import AbstractHttpSession

cookies_filename = "cookies.pickle"

default_logger = getLogger(__name__)


class ResponseContext:
    """
    Response that doubles as an awaitable and a context manager.

    Same kind of thing that aiohttp uses for its responses, but theirs isn't
    part of their public API so we replicate it here. This acts as a wrapper
    around their thing.

    Also, we add functionality for configuring a post-exit callback, so there
    is some justification for having it here again beyond reimplementing a
    private class...
    """

    def __init__(self, aiohttp_response_context, post_request_cb=lambda: None):
        self.aiohttp_response_context = aiohttp_response_context
        self.post_request_cb = post_request_cb

    async def __aenter__(self) -> aiohttp.ClientResponse:
        return await self.aiohttp_response_context.__aenter__()

    async def __aexit__(self, *args, **kwargs) -> None:
        return await self.aiohttp_response_context.__aexit__(*args, **kwargs)

    async def __await__(self) -> aiohttp.ClientResponse:
        try:
            r = await self.aiohttp_response_context.__await__()
        finally:
            self.post_request_cb()
        return r


def context_manager_to_response_context(cm):
    @wraps(cm)
    def _cm(*args, **kwargs):
        context = cm(*args, **kwargs)
        inner_response_context = context.__enter__()
        return ResponseContext(inner_response_context, context.__exit__)

    return _cm


T = TypeVar("T", bound="PersistingHttpClientSession")


class PersistingHttpClientSession(AbstractHttpSession):
    """
    Async HTTP client session that persists cookies to disk after each request.

    Approximates an actual browser's behavior w/r/t to cookie persistence.
    """

    def __init__(
        self,
        inner: AbstractHttpSession,
        persist_to: Path,
        create_parents: bool = True,
        logger: Logger = default_logger,
    ):
        """
        Args:
            inner: Underlying HTTP client session used for everything except
                thje persistence.
            persist_to: Directory in which to persist coookies. They'll be
                placed inside a file named ``cookies.pickle`` inside this
                directory.
            create_parents: Whether to create parent directories of persist_to
                if they don't exist.
        """
        self.inner = inner
        self.persist_to = persist_to
        self.create_parents = create_parents
        self.logger = logger

    @property
    def cookies_path(self) -> Path:
        return self.persist_to / cookies_filename

    @property
    def cookie_jar(self) -> aiohttp.CookieJar:
        return self.inner.cookie_jar

    @classmethod
    def make_loaded(cls: Type[T], *args, **kwargs) -> T:
        """
        Convenience method to construct an instance and load cookies from disk.

        Equivalent to instantiating and then calling ``load`` while suppressing
        and logging errors.
        """
        obj = cls(*args, **kwargs)
        obj.load(suppress_errors=True)
        return obj

    def load(self, suppress_errors: bool = False) -> None:
        """
        Load cookies for the inner session from disk.

        Args:
            suppress_errors: Whether to suppress errors when loading the
                cookies from disk. Doesn't suppress all errors, only those
                caused by e.g. faulty I/O and missing or malformed files.
        """
        cookie_jar = aiohttp.CookieJar()
        try:
            cookie_jar.load(self.cookies_path)
        except Exception:
            # TODO add proper logging using logging module instead
            print_exc()
            warn(
                f"error reading pickled cookies at {self.cookies_path} "
                "- ignoring"
            )
        self.inner.cookie_jar.update_cookies(
            (cookie.key, cookie) for cookie in cookie_jar
        )

    def save(self):
        """
        Persist current session cookies to disk.
        """
        self.persist_to.mkdir(exist_ok=True, parents=self.create_parents)
        # save cookies using provided method (dumb b/c uses pickle but oh well)
        self.inner.cookie_jar.save(self.cookies_path)

    @context_manager_to_response_context
    @contextmanager
    def get(self, *args, **kwargs):
        self.logger.debug("GET: %r, %r", args, kwargs)
        response_context = self.inner.get(*args, **kwargs)
        try:
            yield response_context
        finally:
            self.save()

    @context_manager_to_response_context
    @contextmanager
    def post(self, *args, **kwargs):
        self.logger.debug("POST: %r, %r", args, kwargs)
        response_context = self.inner.post(*args, **kwargs)
        try:
            yield response_context
        finally:
            self.save()

    # ... add more methods here as the need arises
