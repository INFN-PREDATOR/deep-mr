"""Image IO routines."""

from . import dicom as _dicom
# from . import nifti as _nifti

from .dicom import *  # noqa

__all__ = []
__all__.extend(_dicom.__all__)


