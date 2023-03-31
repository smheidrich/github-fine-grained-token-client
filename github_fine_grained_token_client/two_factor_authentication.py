import asyncio
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor


class TwoFactorOtpProvider(ABC):
    """
    Two-factor authentication (2FA) one-time password (OTP) provider.
    """

    @abstractmethod
    async def get_otp_for_user(self, username: str) -> str:
        """
        Get a 2FA OTP for the given username.

        This could e.g. prompt the user for it via the terminal when used in a
        CLI application or via a dialog when used in a GUI application, or it
        could interact with the necessary services in an automated manner,
        pretending to be a separate device (which would kind of defeat the
        point of 2FA...).

        Args:
            username: Username for which to get the OTP.

        Returns:
            The OTP.
        """
        pass


class NullTwoFactorOtpProvider(TwoFactorOtpProvider):
    """
    OTP provider that will just raise an error when an OTP is requested.

    Only useful as long as 2FA is still not mandatory on GitHub (i.e. until end
    of Q1 2023).
    """

    async def get_otp_for_user(self, username: str) -> str:
        raise RuntimeError(
            "OTP for two-factor authentication requested, "
            'but "dummy" provider configured'
        )


class BlockingPromptTwoFactorOtpProvider(TwoFactorOtpProvider):
    """
    OTP provider that blockingly prompts the user for an OTP on the terminal.
    """

    async def get_otp_for_user(self, username: str) -> str:
        return input(f"2FA OTP for user {username!r}: ")


class ThreadedPromptTwoFactorOtpProvider(TwoFactorOtpProvider):
    """
    OTP provider that prompts the user for an OTP on the terminal in a thread.

    This makes it non-blocking, but because it generally spawns a *new* thread
    for prompting the user (via the async event loop's thread pool), it might
    not play nicely with programs using multiprocessing (e.g. if a new process
    is forked while the thread is still running).

    **NOTE** also that this will hang indefinitely if the main thread exits,
    preventing the program from exiting. See
    `here <https://stackoverflow.com/a/49992422>`_ for why. I hope future
    Python versions will provide a way to have true daemon threads awaited on
    via ``asyncio``.
    """

    @staticmethod
    def _thread_target(self, username: str) -> str:
        return input(f"2FA OTP for user {username!r}: ")

    # TODO This will freeze the whole application if the main thread exits
    # because ThreadPoolExecutor doesn't spawn true daemon threads... See the
    # NOTE above. => Python feature request?
    async def get_otp_for_user(self, username: str) -> str:
        return await asyncio.get_running_loop().run_in_executor(
            ThreadPoolExecutor(), self._thread_target
        )
