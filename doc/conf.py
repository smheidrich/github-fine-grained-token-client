# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = "github-fine-grained-token-client"
copyright = "2023, smheidrich <smheidrich@weltenfunktion.de>"
author = "smheidrich <smheidrich@weltenfunktion.de>"

# The full version, including alpha/beta/rc tags
release = "2023"


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    # "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.intersphinx",
    # "sphinx.ext.autosummary",
    # "autoapi.extension",
    # "sphinxcontrib.repl_selectability",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "alabaster"

# Options for theme
html_theme_options = {
    "page_width": "960px",
    # 'logo': 'logo.png',
    # 'logo_name': True,
    # 'logo_text_align': 'center',
}

# html_favicon = '_static/favicon.png'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]


# -- Autodoc configuration ---------------------------------------------------

# don't show argument type hints in function signature, which looks really bad
# - show in description instead
autodoc_typehints = "description"

# -- Intersphinx configuration -----------------------------------------------

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

# -- Cross-referencing defaults ----------------------------------------------

# default_role = 'any'

# -- AutoAPI configuration ---------------------------------------------------

autoapi_type = "python"
autoapi_dirs = ["../github_fine_grained_token_client"]
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
    "special-members",
    "imported-members",
]
