"""Sub-package containing basic signal and tensor manipulation routines.

Basic routines include tensor resizing (crop and pad),
resampling (up- and downsampling), filtering, wavelet and low rank decompsition.

"""
from . import filter as _filter
from . import fold as _fold

from . import resize as _resize
from . import subspace as _subspace
from . import wavelet as _wavelet

from .filter import *  # noqa
from .fold import *  # noqa
from .resize import *  # noqa
from .subspace import *  # noqa
from .wavelet import *  # noqa

__all__ = []
__all__.extend(_filter.__all__)
__all__.extend(_fold.__all__)
__all__.extend(_resize.__all__)
__all__.extend(_subspace.__all__)
__all__.extend(_wavelet.__all__)
