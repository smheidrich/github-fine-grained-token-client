github-fine-grained-token-client
================================

github-fine-grained-token-client is a library and CLI tool for creating and
managing GitHub's fine-grained personal access tokens tokens.

Purpose
-------

GitHub allows the creation of per-project access tokens with fine-grained
permissions but `doesn't currently have an API
<https://github.com/community/community/discussions/36441#discussioncomment-3908915>`_
to do so.

This tool seeks to provide a client exposing this functionality anyway by
whatever means necessary. More specifically, for now this means simulating
requests to the relevant parts of the web interface closely enough to how a
browser would perform them.


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
