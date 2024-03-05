"""
"""
# read version from installed package
from importlib.metadata import version

__version__ = version("deepmr")

from . import bloch
from . import io
from . import fft
from . import linops

# from . import optim
# from . import prox
from .testdata import testdata
from ._types import Header

from . import _signal
from . import _vobj

from ._signal import *  # noqa
from ._vobj import *  # noqa

__all__ = [testdata, Header]
__all__.extend(_signal.__all__)
__all__.extend(_vobj.__all__)
