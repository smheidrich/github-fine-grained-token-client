# github-fine-grained-token-client

[![pipeline status](https://gitlab.com/smheidrich/github-fine-grained-token-client/badges/main/pipeline.svg?style=flat-square)](https://gitlab.com/smheidrich/github-fine-grained-token-client/-/commits/main)
[![docs](https://img.shields.io/badge/docs-online-brightgreen?style=flat-square)](https://smheidrich.gitlab.io/github-fine-grained-token-client/)
[![pypi](https://img.shields.io/pypi/v/github-fine-grained-token-client)](https://pypi.org/project/github-fine-grained-token-client/)
[![supported python versions](https://img.shields.io/pypi/pyversions/github-fine-grained-token-client)](https://pypi.org/project/github-fine-grained-token-client/)

Library and CLI tool for creating and managing fine-grained GitHub tokens.

## Purpose

GitHub allows the creation of per-project access tokens with fine-grained
permissions but
[doesn't currently have an API](https://github.com/community/community/discussions/36441#discussioncomment-3908915)
to do so.

This tool seeks to provide a client exposing this functionality anyway by
whatever means necessary. More specifically, for now this means simulating
requests to the relevant parts of the web interface closely enough to how a
browser would perform them.

## Installation

To install from PyPI:

```bash
pip3 install github-fine-grained-token-client
```

## Command-line tool usage

To use the CLI tool, you'll need to install some optional dependencies first:

```bash
pip3 install 'github-fine-grained-token-client[cli]'
```

To create a token `yourtokenname` with read-only permissions (the default) for
your public GitHub repository `yourrepo`:

```bash
github-fine-grained-token-client create --repositories yourrepo yourtokenname
```

There are more commands and options - please refer to the docs.

## Usage as a library

Basic example script:

```python
import asyncio
from datetime import timedelta
from os import environ

from github_fine_grained_token_client import (
    BlockingPromptTwoFactorOtpProvider,
    GithubCredentials,
    SelectRepositories,
    async_client,
)

credentials = GithubCredentials(environ["GITHUB_USER"], environ["GITHUB_PASS"])
assert credentials.username and credentials.password


async def main() -> str:
    async with async_client(
        credentials=credentials,
        # 2FA will be mandatory on GitHub starting at some point in 2023
        two_factor_otp_provider=BlockingPromptTwoFactorOtpProvider(),
    ) as session:
        token = await session.create_token(
            "my token",
            expires=timedelta(days=364),
            scope=SelectRepositories(["my-project"]),
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
