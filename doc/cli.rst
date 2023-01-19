Command-line usage
==================

Installing the package will install the ``github-token-client`` command-line
interface (CLI) tool that can be used to generate, list and delete GitHub tokens.

This page contains some basic instructions, but for more detailed information
you can also check ``github-token-client --help``.

Basic usage
-----------

To create a new project-scoped token, you can simply do

.. code:: bash

   github-token-client create --project yourproject yourtokenname

The tool will prompt you for your GitHub username and password so it can log in,
ask whether it should save your credentials to the system keyring (see below)
and, if everything works, create and print a new token named ``yourtokenname``
for a project named ``yourproject``.

Note: This project must already exist before a token can be created for it. As
far as I know, the only way to create a new project on GitHub is to upload a
package using e.g. Twine.

Keyring (optional)
------------------

After the first login with a new username (or previously used username but new
password) succeeds, ``github-token-client`` will ask you whether it should save
the used credentials to the system keyring.

Refer to the `keyring package's README <https://github.com/jaraco/keyring>`_
for how to configure which keyring backend to use, including the "null" backend
which simply disabled this functionality altogether.

If you select yes, it won't have to ask you for the password the next time you
use it, as it will just be taken from this keyring.

It will ask again for the username, however, in order to be explicit in case of
multiple accounts. This behavior could be changed in the future so a default
account will be used unless explicitly overridden.

Other ways to provide credentials
---------------------------------

It's not always desirable to provide credentials via a prompt, e.g. when you're
using the script in an automated manner. In these cases, you can provide
credentials in a non-interactive manner instead.

Note that providing both the username and password in this way will disable the
keyring prompt as well.

Command-line arguments
~~~~~~~~~~~~~~~~~~~~~~

If you don't want to type in your username each time, one way is to specify it
as a command-line argument with ``--username`` / ``-u``:

.. code:: bash

   github-token-client -u yourusername create --project yourproject yourtoken

Technically, this is also possible for the password, but doing so is **not**
recommended, as it will expose the password via the process's metadata
(visible e.g. in ``ps -eo args``).

Environment variables
~~~~~~~~~~~~~~~~~~~~~

Every CLI option has a corresponding environment variable named according to
the schema ``GITHUBTOKENCLIENT_<name of the cli option>``.
So it's also possible to provide a username and password by setting
``GITHUBTOKENCLIENT_USERNAME`` and ``GITHUBTOKENCLIENT_PASSWORD``.

Troubleshooting
---------------

If anything goes wrong (e.g. errors messages appear), you can run the CLI tool
with the ``--no-headless`` option to run the browser in non-headless mode and
be able to view what happens.

More commands
-------------

In addition to creating tokens, the tool also supports these operations:

Listing tokens
~~~~~~~~~~~~~~

To list all tokens for a GitHub account:

.. code:: bash

   github-token-client list

Note: The format of this is currently just printed Python dataclasses, which
will change in the future. Don't rely on the format, use the API instead.

Deleting tokens
~~~~~~~~~~~~~~~

To delete a token from GitHub:

.. code:: bash

   github-token-client delete yourtokenname
