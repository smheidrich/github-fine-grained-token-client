API Reference
=============

``github_fine_grained_token_client`` package
--------------------------------------------

``async`` client
~~~~~~~~~~~~~~~~

.. autofunction:: github_fine_grained_token_client.async_github_fine_grained_token_client

.. autoclass:: github_fine_grained_token_client.AsyncGithubFineGrainedTokenClientSession
   :members:
   :inherited-members:
   :undoc-members:

Credentials
~~~~~~~~~~~

.. autoclass:: github_fine_grained_token_client.GithubCredentials
   :members:
   :inherited-members:
   :undoc-members:

Two-factor authentication (2FA)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One-time password (OTP) providers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: github_fine_grained_token_client.TwoFactorOtpProvider
   :members:
   :inherited-members:
   :undoc-members:

.. autoclass:: github_fine_grained_token_client.NullTwoFactorOtpProvider
   :members:
   :inherited-members:
   :undoc-members:

.. autoclass:: github_fine_grained_token_client.BlockingPromptTwoFactorOtpProvider
   :members:
   :inherited-members:
   :undoc-members:

.. autoclass:: github_fine_grained_token_client.ThreadedPromptTwoFactorOtpProvider
   :members:
   :inherited-members:
   :undoc-members:

Token scopes
~~~~~~~~~~~~

.. autoclass:: github_fine_grained_token_client.FineGrainedTokenScope
   :members:
   :inherited-members:
   :undoc-members:

.. autoclass:: github_fine_grained_token_client.AllRepositories
   :members:
   :inherited-members:
   :undoc-members:

.. autoclass:: github_fine_grained_token_client.PublicRepositories
   :members:
   :inherited-members:
   :undoc-members:

.. autoclass:: github_fine_grained_token_client.SelectRepositories
   :members:
   :inherited-members:
   :undoc-members:

Permissions
~~~~~~~~~~~

A single permission consists of two parts: A "permission key" (term I made up,
nowhere to be found in GitHub's docs) describing the resource(s) to which it
applies and a "permission value" describing the level of access granted (none,
read-only, read/write).

Permission keys
^^^^^^^^^^^^^^^

Permission keys are grouped into account permissions and repository
permissions. If you want a type to reference either, you can use the
:any:`AnyPermissionKey` type alias.

Enum members of the constituent types always have attributes ``value``
(corresponding to the identifier used for communicating with GitHub's servers,
which is also used to represent them in this package's CLI tool) and
``full_name`` corresponding to a human-readable name.

.. autoclass:: github_fine_grained_token_client.AnyPermissionKey

.. autoenum:: github_fine_grained_token_client.AccountPermission

.. autoenum:: github_fine_grained_token_client.RepositoryPermission

Permission values
^^^^^^^^^^^^^^^^^

.. autoenum:: github_fine_grained_token_client.PermissionValue

Token information bundles
~~~~~~~~~~~~~~~~~~~~~~~~~

These are "bundles" of different sets of information about a token that are
returned by different methods. There are so many of them because different
calls will yield different amounts of information and in my opinion the types
should fit "tightly" over that to make maximal use of static type checking.

.. autoclass:: github_fine_grained_token_client.FineGrainedTokenMinimalInfo
   :members:
   :inherited-members:
   :undoc-members:

.. autoclass:: github_fine_grained_token_client.FineGrainedTokenBulkInfo
   :members:
   :inherited-members:
   :undoc-members:

.. autoclass:: github_fine_grained_token_client.FineGrainedTokenStandardInfo
   :members:
   :inherited-members:
   :undoc-members:

.. autoclass:: github_fine_grained_token_client.FineGrainedTokenIndividualInfo
   :members:
   :inherited-members:
   :undoc-members:

.. autoclass:: github_fine_grained_token_client.FineGrainedTokenCompletePersistentInfo
   :members:
   :inherited-members:
   :undoc-members:


Exceptions
~~~~~~~~~~

.. autoexception:: github_fine_grained_token_client.LoginError
   :members:
   :undoc-members:

.. autoexception:: github_fine_grained_token_client.UsernameError
   :members:
   :undoc-members:

.. autoexception:: github_fine_grained_token_client.PasswordError
   :members:
   :undoc-members:

.. autoexception:: github_fine_grained_token_client.TooManyAttemptsError
   :members:
   :undoc-members:

.. autoexception:: github_fine_grained_token_client.TwoFactorAuthenticationError
   :members:
   :undoc-members:

.. autoexception:: github_fine_grained_token_client.TokenCreationError
   :members:
   :undoc-members:

.. autoexception:: github_fine_grained_token_client.TokenNameError
   :members:
   :undoc-members:

.. autoexception:: github_fine_grained_token_client.TokenNameAlreadyTakenError
   :members:
   :undoc-members:

.. autoexception:: github_fine_grained_token_client.RepositoryNotFoundError
   :members:
   :undoc-members:
