from abc import ABC, abstractmethod

import aiohttp


class AbstractHttpSession(ABC):
    @property
    @abstractmethod
    def cookie_jar(self) -> aiohttp.CookieJar:
        pass

    # see https://github.com/aio-libs/aiohttp/issues/7247 for why we use a
    # private type for the return values below...

    @abstractmethod
    def get(self, *args, **kwargs) -> aiohttp.client._RequestContextManager:
        pass

    @abstractmethod
    def post(self, *args, **kwargs) -> aiohttp.client._RequestContextManager:
        pass
