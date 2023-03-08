Library usage
=============

Basic example
-------------

Here is a basic example script showing how to use the library's ``async``
client to create a new token on GitHub:

.. code:: python

    import asyncio
    from os import getenv

    from github_fine_grained_token_client import (
      async_github_fine_grained_token_client, SingleProject, GithubCredentials
    )

    credentials = GithubCredentials(getenv("GITHUB_USER"), getenv("GITHUB_PASS"))
    assert credentials.username and credentials.password

    async def main() -> str:
      async with async_github_fine_grained_token_client(credentials) as session:
          token = await session.create_token(
              "my token",
              SingleProject("my-project"),
          )
      return token

    token = asyncio.run(main())

    print(token)

This is just a basic example, further information can be found in the :ref:`API
Reference`.

Non-async/synchronous client
----------------------------

There is no non-async (e.g. blocking) variant of the client yet - if you would
like one, please open an issue to let me know and I'll try to add one (it's not
a problem for me, there is just no point doing it if nobody needs it).
