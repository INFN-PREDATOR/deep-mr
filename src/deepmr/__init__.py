# read version from installed package
from importlib.metadata import version
__version__ = version("deepmr")

from . import io
from .testdata import testdata