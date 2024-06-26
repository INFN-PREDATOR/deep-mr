# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

for x in os.walk("../../src"):
    sys.path.insert(0, os.path.abspath(x[0]))

# -- Project information -----------------------------------------------------

project = "deepmr"
copyright = "2023, Matteo Cencini"
author = "Matteo Cencini"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "matplotlib.sphinxext.plot_directive",
    "myst_parser",
    "nbsphinx",
    "sphinx_gallery.load_style",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]
autosummary_generate = True
autosummary_imported_members = True

intersphinx_mapping = {
    "numpy": ("http://docs.scipy.org/doc/numpy/", None),
    "torch": ("https://docs.pytorch.org/2.0/", None),
    "python": ("https://docs.python.org/3.4", None),
}

autodoc_mock_imports = [
    "dacite",
    "deepinv",
    "h5py",
    "ismrmrd",
    "mat73",
    "matplotlib",
    "nibabel",
    "numpy",
    "numba",
    "pydicom",
    "pywt",
    "ptwt",
    "scipy",
    "torch",
    "tqdm",
]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_book_theme"
html_theme_options = {
    "repository_url": "https://github.com/INFN-PREDATOR/deep-mr",
    "use_repository_button": True,
    "use_issues_button": True,
    "use_edit_page_button": True,
    "use_download_button": True,
    "home_page_in_toc": True,
    "logo": {
        "image_light": "https://github.com/INFN-PREDATOR/deep-mr/blob/main/docs/source/figures/deepmr_logo.png?raw=true",
        "image_dark": "https://github.com/INFN-PREDATOR/deep-mr/blob/main/docs/source/figures/deepmr_logo_dark.png?raw=true",
        "scale": "10%",
    },
}
