from aiohttp import ClientResponse, ClientSession

cookies_filename = "cookies.pickle"


class ResponseHoldingHttpSession:
    """
    Async HTTP client session that holds onto the last response it got.

    This helps with releasing the response when no longer needed, which in turn
    helps with connection re-use.

    Basically it takes the decision of when to release the response out of the
    user's hands, always releasing it before a new request.

    This implies that unlike those of ``aiohttp`` sessions, request methods
    like ``get`` and ``post`` do *not* return objects that can be used as async
    context managers!
    """

    def __init__(self, inner: ClientSession):
        """
        Args:
            inner: Underlying HTTP client session.
        """
        self.inner = inner
        self.response: ClientResponse | None = None

    # TODO add an __aexit__ for this?
    async def _release_optional_response(self):
        if self.response is not None:
            await self.response.release()

    async def get(self, *args, **kwargs) -> ClientResponse:
        await self._release_optional_response()
        self.response = await self.inner.get(*args, **kwargs)
        return self.response

    async def post(self, *args, **kwargs) -> ClientResponse:
        await self._release_optional_response()
        self.response = await self.inner.post(*args, **kwargs)
        return self.response

    # ... add more methods here as the need arises
