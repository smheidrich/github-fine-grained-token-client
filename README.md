# github-fine-grained-token-client

[![pipeline status](https://gitlab.com/smheidrich/github-fine-grained-token-client/badges/main/pipeline.svg?style=flat-square)](https://gitlab.com/smheidrich/github-fine-grained-token-client/-/commits/main)
[![docs](https://img.shields.io/badge/docs-online-brightgreen?style=flat-square)](https://smheidrich.gitlab.io/github-fine-grained-token-client/)
[![pypi](https://img.shields.io/pypi/v/github-fine-grained-token-client)](https://pypi.org/project/github-fine-grained-token-client/)
[![supported python versions](https://img.shields.io/pypi/pyversions/github-fine-grained-token-client)](https://pypi.org/project/github-fine-grained-token-client/)

Library and CLI tool for creating and managing GitHub project tokens.

## Purpose

GitHub allows the creation of per-project tokens but doesn't (AFAIK) currently
have an API to do so.

This tool seeks to provide a client exposing this functionality anyway by
whatever means necessary.

## Operating principle

Because there is no API and I'm also too lazy to try and figure out the exact
sequence of HTTP requests one would have to make to simulate what happens when
requesting tokens on the GitHub website, for now this tool just uses
[Playwright](https://playwright.dev/python/) to automate performing the
necessary steps in an *actual* browser.

This might be overkill and brittle but it works for now 🤷

## Installation

To install from PyPI:

```bash
pip3 install github-fine-grained-token-client
```

You'll also have to install the required Playwright browsers (currently just
Chromium):

```bash
playwright install chromium
```

## Command-line tool usage

To create a token `yourtokenname` for your GitHub project `yourproject`:

```bash
github-fine-grained-token-client create --project yourproject yourtokenname
```

There are more commands - please refer to the docs.

## Usage as a library

Basic example script:

```python
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
```

## More information

For more detailed usage information and the API reference, refer to
[the documentation](https://smheidrich.gitlab.io/github-fine-grained-token-client/).

## License

MIT License, see `LICENSE` file.
