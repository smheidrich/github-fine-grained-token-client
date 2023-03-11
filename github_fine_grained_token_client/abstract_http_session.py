from abc import ABC, abstractmethod

from aiohttp import CookieJar


class AbstractHttpSession(ABC):
    @property
    @abstractmethod
    def cookie_jar(self) -> CookieJar:
        pass

    @abstractmethod
    async def get(self, *args, **kwargs):
        pass

    @abstractmethod
    async def post(self, *args, **kwargs):
        pass
