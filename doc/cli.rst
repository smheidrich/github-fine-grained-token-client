Command-line usage
==================

The package comes with a command-line interface (CLI) tool named
``github-fine-grained-token-client`` that can be used to generate, list and
delete GitHub tokens.

Installation
------------

The executable itself is automatically installed into your Python interpreter's
preferred executable directory (e.g. ``~/.local/bin`` when installing for the
current user only) when you install the ``github-fine-grained-token-client``
package, but in order to actually be able to use it, you first have to install
its optional ``cli`` dependencies ("extras"):

.. code:: bash

   pip3 install 'github-fine-grained-token-client[cli]'

Basic usage
-----------

This section is meant to explain some things common to all operations supported
by the tool. More details on the available commands can be found in the section
further below and in the output of ``github-fine-grained-token-client --help``.

To illustrate the basic functioning of the CLI tool, let's just list all (if
any) fine-grained tokens associaed with a GitHub account:

.. code:: bash

   github-fine-grained-token-client list

The tool will prompt you for your GitHub username and password so it can log
in, ask whether it should save your credentials to the system keyring (see
below) and, if everything works, create and print a new token named
``yourtokenname`` with the stated settings.
It will also prompt for a two-factor authentication (2FA) one-time password
(OTP) if you have 2FA configured (which will be mandatory on GitHub starting at
some point in 2023).

Keyring (optional)
------------------

After the first login with a new username (or with a previously used username
but a new password) succeeds, ``github-fine-grained-token-client`` will ask you
whether it should save the used credentials to the system keyring.

Refer to the `keyring package's README <https://github.com/jaraco/keyring>`_
for how to configure which keyring backend to use, including the "null" backend
which simply disabled this functionality altogether.

If you select yes, it won't have to ask you for the password the next time you
use it, as it will just be taken from this keyring.

It will ask again for the username, however, in order to be explicit in case of
multiple accounts (see next section for ways to get around this). This behavior
could be changed in the future so a default account will be used unless
explicitly overridden.

Other ways to provide credentials
---------------------------------

It's not always desirable to provide credentials via a prompt, e.g. when you're
using the script in an automated manner. In these cases, you can provide
credentials in non-interactively instead, which can be done in two different
ways as outlined in the following subsections.

Note that providing *both* the username and password non-interactively will
implicitly disable the keyring functionality altogether, so the credentials
won't be saved saved to a keyring (which is probably what you want, as
non-interactive credentials imply you have your own external mechanism for
storing them securely).

Command-line arguments
~~~~~~~~~~~~~~~~~~~~~~

To provide only the username non-interactively, you can specify it as a
command-line argument with ``--username`` / ``-u``:

.. code:: bash

   github-fine-grained-token-client -u yourusername list

Technically, this is also possible for the password, but doing so is **not**
recommended, as it will expose the password via the process's metadata (visible
e.g. in the output of ``ps -eo args``, including to other processes).

Environment variables
~~~~~~~~~~~~~~~~~~~~~

Every CLI option has a corresponding environment variable named according to
the schema ``GITHUBFINEGRAINEDTOKENCLIENT_<name of the cli option>``.
So it's also possible to provide a username and password by setting
``GITHUBFINEGRAINEDTOKENCLIENT_USERNAME`` and
``GITHUBFINEGRAINEDTOKENCLIENT_PASSWORD``.

Session persistence (cookies)
-----------------------------

To reduce the number of times you have to authenticate via 2FA and to speed up
the login process by reducing the number of necessary steps, you can let the
application persist its GitHub cookies to your filesystem:

.. code:: bash

   github-fine-grained-token-client \
      -u yourusername \
      --persist ~/.github-token-client/cookies \
      list

This will store the session cookies in your ``~/.github-token-client/cookies``
directory on exit. The next time you run the command, it will load them from
there, allowing it to skip the login and 2FA so long as the last execution
wasn't too long ago (GitHub resets the 2FA status of the session after some
time at which point you'll have to do it anyway).

More commands & command details
-------------------------------

In this section we go through the available commands in more detail.

Creating tokens
~~~~~~~~~~~~~~~

To create, for example, a new fine-grained token with write access to the code
(contents) and issues of a repository named ``yourproject``, plus read access
to its deployments, you can do:

.. code:: bash

   github-fine-grained-token-client create \
      --repositories yourproject \
      --write-permissions contents,issues \
      --read-permissions deployments \
      yourtokenname

As you can see, the permissions are always comma-separated (make sure there are
no spaces before or after the commas!). A full list of available permissions
can be obtained with the ``possible-permissions`` command:

.. code:: bash

   github-fine-grained-token-client possible-permissions

To find out what each of them mean, refer to the token creation page on
GitHub's website (you can usually guess which is which by the name).
Integrating this command plus the descriptions into the help text will be done
in a future release.

For less verbosity when running the tool manually, you might want to use short
options instead (``-r`` for ``--repositories``, ``-W`` for
``write-permissions``, and ``-R`` for  ``--read-permissions``):

.. code:: bash

   github-fine-grained-token-client create \
      -r yourproject \
      -W contents,issues \
      -R deployments \
      yourtokenname

But you should use the long options when using the tool in scripts, as they are
easier for readers to understand and are more likely to be backwards-compatible
even between major versions.

Note that if no repository is specified, the token will be created for all
*public* repositories, which also forces it to be read-only. This is the option
selected by default on GitHub's website, so it's also the default here.

If you want to create a token that's valid for *all* repositories for whatever
reason, you can use the ``--all-repositories`` (short: ``-a``) option, e.g.:

.. code:: bash

   github-fine-grained-token-client create -a -W contents yourtokenname

Listing tokens
~~~~~~~~~~~~~~

We've already seen this one above, and that was pretty much all there is to it.
But again for completeness's sake: To list all fine-grained tokens for a GitHub
account, you can do:

.. code:: bash

   github-fine-grained-token-client list

Note: Please don't rely on the output format staying the same between versions
of this package. Use the package as a library instead (I might implement a
``--porcelain`` switch in the future though).

Deleting tokens
~~~~~~~~~~~~~~~

To delete a fine-grained token from GitHub:

.. code:: bash

   github-fine-grained-token-client delete yourtokenname
