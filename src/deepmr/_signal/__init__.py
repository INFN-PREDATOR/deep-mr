"""Sub-package containing basic signal and tensor manipulation routines.

Basic routines include tensor resizing (crop and pad),
resampling (up- and downsampling), filtering and low rank decompsition.

"""
from . import resize as _resize
from . import patch as _patch
from . import filter as _filter
from . import interp as _interp

from .patch import *  # noqa
from .resize import *  # noqa
from .filter import *  # noqa
from .interp import *  # noqa
from .sparse import *  # noqa

__all__ = []
__all__.extend(_patch.__all__)
__all__.extend(_resize.__all__)
__all__.extend(_filter.__all__)
__all__.extend(_interp.__all__)
