import asyncio
from functools import wraps


def top_level_sync(func):
    """
    Decorator to automatically run async functions in a new event loop.

    This effectively makes them synchronous, but means they can't be called
    from within other async functions (hence "top level" in the name).
    Sometimes that is just fine.
    """

    @wraps(func)
    def func2(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return func2
