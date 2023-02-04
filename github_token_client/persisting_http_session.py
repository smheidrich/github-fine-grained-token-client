from pathlib import Path
from traceback import print_exc
from warnings import warn

from aiohttp import ClientSession, CookieJar

cookies_filename = "cookies.pickle"


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
        self._load()

    def _load(self):
        cookies_path = self.persist_to / cookies_filename
        cookie_jar = CookieJar()
        try:
            cookie_jar.load(cookies_path)
            self.inner.cookie_jar.update_cookies(
                (cookie.key, cookie) for cookie in cookie_jar
            )
        except Exception:
            # TODO add proper logging using logging module instead
            print_exc()
            warn(f"error reading pickled cookies at {cookies_path} - ignoring")
            return None

    def _persist(self):
        """
        Persist current session cookies to disk.
        """
        self.persist_to.mkdir(exist_ok=True, parents=self.create_parents)
        # save cookies using provided method (dumb b/c uses pickle but oh well)
        self.inner.cookie_jar.save(self.persist_to / cookies_filename)

    async def get(self, *args, **kwargs):
        response = await self.inner.get(*args, **kwargs)
        self._persist()
        return response

    async def post(self, *args, **kwargs):
        response = await self.inner.post(*args, **kwargs)
        self._persist()
        return response

    # ... add more methods here as the need arises
