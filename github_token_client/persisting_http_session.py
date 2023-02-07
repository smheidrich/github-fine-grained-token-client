from pathlib import Path
from traceback import print_exc
from typing import Type, TypeVar
from warnings import warn

from aiohttp import ClientSession, CookieJar

cookies_filename = "cookies.pickle"

T = TypeVar("T")


class PersistingHttpClientSession:
    """
    Async HTTP client session that persists cookies to disk after each request.

    Approximates an actual browser's behavior w/r/t to cookie persistence.
    """

    def __init__(
        self,
        inner: ClientSession,
        persist_to: Path,
        create_parents: bool = True,
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

    @property
    def cookies_path(self) -> Path:
        return self.persist_to / cookies_filename

    @classmethod
    def make_loaded(cls: Type[T], *args, **kwargs) -> T:
        """
        Convenience method to construct an instance and load cookies from disk.

        Equivalent to instantiating and then calling ``load`` while suppressing
        and logging errors.
        """
        try:
            obj = cls(*args, **kwargs)
            obj.load()
        except Exception:
            # TODO add proper logging using logging module instead
            print_exc()
            warn(
                f"error reading pickled cookies at {obj.cookies_path} "
                "- ignoring"
            )
        return obj

    def load(self) -> None:
        """
        Load cookies for the inner session from disk.
        """
        cookie_jar = CookieJar()
        cookie_jar.load(self.cookies_path)
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

    async def get(self, *args, **kwargs):
        response = await self.inner.get(*args, **kwargs)
        self.save()
        return response

    async def post(self, *args, **kwargs):
        response = await self.inner.post(*args, **kwargs)
        self.save()
        return response

    # ... add more methods here as the need arises
