github-token-client
=================

github-token-client is a library and CLI tool for creating and managing GitHub
project tokens.

Purpose
-------

GitHub allows the creation of per-project tokens but doesn't (AFAIK) currently
have an API to do so.

This tool seeks to provide a client exposing this functionality anyway by
whatever means necessary.

Operating principle
-------------------

Because there is no API and I'm also too lazy to try and figure out the exact
sequence of HTTP requests one would have to make to simulate what happens when
requesting tokens on the GitHub website, for now this tool just uses
`Playwright <https://playwright.dev/python/>`_ to automate performing the
necessary steps in an *actual* browser.

This might be overkill and brittle but it works for now 🤷


Table of contents
-----------------

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   cli
   library
   reference


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
