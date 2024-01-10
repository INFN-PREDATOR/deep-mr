"""Sub-package containing regularization routines.

DeepMR provides regularization routines for compressed sensing.
All the routines are based on the excellent Deep Inverse (https://github.com/deepinv/deepinv) package.

"""

from deepinv.models import BM3D, TV, TGV

from . import llr as _llr
from . import wavelet as _wavelet

from .llr import * # noqa
from .wavelet import *  # noqa

__all__ = ["BM3D", "TV", "TGV"]

# __all__.extend(_llr.__all__)
__all__.extend(_wavelet.__all__)

