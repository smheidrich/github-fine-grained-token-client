Library usage
=============

Here is a basic example script showing how to use the library's ``async``
client to create a new token on GitHub:

.. code:: python

    import asyncio
    from os import getenv

    from github_token_client import (
      async_github_token_client, SingleProject, GithubCredentials
    )

    credentials = GithubCredentials(getenv("GITHUB_USER"), getenv("GITHUB_PASS"))
    assert credentials.username and credentials.password

    async def main() -> str:
      async with async_github_token_client(credentials) as session:
          token = await session.create_token(
              "my token",
              SingleProject("my-project"),
          )
      return token

    token = asyncio.run(main())

    print(token)

Further information can be found in the :ref:`API Reference`.
