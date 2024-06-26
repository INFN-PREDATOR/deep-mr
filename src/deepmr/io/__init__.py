"""Sub-package containing reading/writing routines.

DeepMR provides reading and writing routines for common k-space
(currently ISMRMRD, GEHC) and image space (DICOM, NIfTI) formats.

"""

from . import generic as _generic
from . import header as _header
from . import image as _image
from . import kspace as _kspace

from .generic import *  # noqa
from .header import *  # noqa
from .image import *  # noqa
from .kspace import *  # noqa

__all__ = []
__all__.extend(_generic.__all__)
__all__.extend(_header.__all__)
__all__.extend(_image.__all__)
__all__.extend(_kspace.__all__)
