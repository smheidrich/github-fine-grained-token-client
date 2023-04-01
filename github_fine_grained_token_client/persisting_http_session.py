from contextlib import AbstractContextManager
from logging import Logger, getLogger
from pathlib import Path
from traceback import print_exc
from typing import Type, TypeVar
from warnings import warn

import aiohttp

from .abstract_http_session import AbstractHttpSession

cookies_filename = "cookies.pickle"

default_logger = getLogger(__name__)


S = TypeVar("S", bound="PersistingHttpClientSession")


class PersistingHttpClientSession(AbstractHttpSession, AbstractContextManager):
    """
    Async HTTP client session wrapper that persists cookies to disk on exit.

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
    def make_loaded(cls: Type[S], *args, **kwargs) -> S:
        """
        Convenience method to construct an instance and load cookies from disk.

        Equivalent to instantiating and then calling ``load`` while suppressing
        and logging errors.
        """
        obj = cls(*args, **kwargs)
        obj.load(suppress_errors=True)
        return obj

    def __exit__(self, *args, **kwargs) -> None:
        self.save()

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
            # this has to be within try because they once changed the format in
            # a way that load() succeeded but this failed... could happen again
            self.inner.cookie_jar.update_cookies(
                (cookie.key, cookie) for cookie in cookie_jar
            )
        except Exception:
            # TODO add proper logging using logging module instead
            # TODO make backup in this case because the cookies will be
            #   overwritten by empty stuff if login fails...
            print_exc()
            warn(
                f"error reading pickled cookies at {self.cookies_path} "
                "- ignoring"
            )

    def save(self):
        """
        Persist current session cookies to disk.
        """
        self.persist_to.mkdir(exist_ok=True, parents=self.create_parents)
        # save cookies using provided method (dumb b/c uses pickle but oh well)
        self.inner.cookie_jar.save(self.cookies_path)

    def get(self, *args, **kwargs) -> aiohttp.client._RequestContextManager:
        self.logger.debug("GET: %r, %r", args, kwargs)
        return self.inner.get(*args, **kwargs)

    def post(self, *args, **kwargs) -> aiohttp.client._RequestContextManager:
        self.logger.debug("POST: %r, %r", args, kwargs)
        return self.inner.post(*args, **kwargs)

    # ... add more methods here as the need arises
