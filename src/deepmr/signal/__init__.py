"""Sub-package containing basic signal and tensor manipulation routines.

Basic routines include tensor resizing (crop and pad),
resampling (up- and downsampling), filtering and low rank decompsition.

"""
from . import resize as _resize

from .resize import *  # noqa

__all__ = []
__all__.extend(_resize.__all__)