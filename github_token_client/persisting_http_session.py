from contextlib import asynccontextmanager
from pathlib import Path

from aiohttp import ClientSession

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

    def _persist(self):
        """
        Persist current session cookies to disk.
        """
        self.persist_to.mkdir(exist_ok=True, parents=self.create_parents)
        # save cookies using provided method (dumb b/c uses pickle but oh well)
        self.inner.cookie_jar.save(self.persist_to / cookies_filename)

    @asynccontextmanager
    async def get(self, *args, **kwargs):
        async with self.inner.get(*args, **kwargs) as response:
            self._persist()
            yield response

    @asynccontextmanager
    async def post(self, *args, **kwargs):
        async with self.inner.post(*args, **kwargs) as response:
            self._persist()
            yield response
