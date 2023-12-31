"""MRD data reading routines."""

__all__ = ["read_mrd"]

import numpy as np
import numba as nb

import ismrmrd

from ..utils import mrd
from ..utils.header import Header
from ..utils.pathlib import get_filepath

def read_mrd(filepath: str, return_ordering: bool = False):
    """
    Read kspace data from mrd file.

    Parameters
    ----------
    filepath : str | list | tuple
        Path to mrd file.
    return_ordering : bool, optional
        If true, return ordering to sort raw data. 
        Useful if sequence is stored separately from raw data.
        The default is False.
    
    Returns
    -------
    data : np.ndarray
        Complex k-space data of shape (ncoils, ncontrasts, nslices, nview, npts).
    traj : np.ndarray
        Sampling trajectory of shape (ncontrasts, nslices, nview, npts).
    dcf : np.ndarray
        Sampling density compensation factor of shape (ncontrasts, nslices, nview, npts, ndims)
    header : deepmr.Header
        Metadata for image reconstruction.
    ordering: np.ndarray, optional
        Re-ordering indexes of shape (nacquisitions, 3), storing
        the contrast, slice and view index (in the column axis), respectively,
        for each acquisition (row) in the dataset. Only returned if 'return_ordering'
        is True.

    """
    # get full path
    filepath = get_filepath(filepath, True, "h5")
    
    # load mrd
    acquisitions, mrdhead = _read_mrd(filepath)
        
    # get all data
    data, traj, dcf = _get_data(acquisitions)
    
    # sort
    data, traj, dcf, ordering = _sort_data(data, traj, dcf, acquisitions, mrdhead)
    
    # get constrats info
    TI = mrd._get_inversion_times(mrdhead)
    TE = mrd._get_echo_times(mrdhead)
    TR = mrd._get_repetition_times(mrdhead)    
    FA = mrd._get_flip_angles(mrdhead)
    
    # get slice locations
    _, firstVolumeIdx, _ = mrd._get_slice_locations(acquisitions)
    
    # build header
    header = Header.from_mrd(mrdhead, acquisitions, firstVolumeIdx)
    
    # update header
    header.FA = FA
    header.TI = TI
    header.TE = TE
    header.TR = TR
        
    if return_ordering:
        return data, traj, dcf, header, ordering
    else:
        return data, traj, dcf, header
        

# %% subroutines
def _read_header(dset):
    xml_header = dset.read_xml_header()
    xml_header = xml_header.decode("utf-8")
    return ismrmrd.xsd.CreateFromDocument(xml_header)


def _read_mrd(filename):
    # open file
    dset = ismrmrd.Dataset(filename)
    
    # read header
    mrdhead = _read_header(dset)
    
    # read acquisitions
    nacq = dset.number_of_acquisitions()
    acquisitions = [dset.read_acquisition(n) for n in range(nacq)]
    
    # close
    dset.close()
    
    return acquisitions, mrdhead


def _get_data(acquisitions):
    data = np.stack([acq.data for acq in acquisitions], axis=0)
    
    if acquisitions[0].traj.size != 0:
        trajdcf = np.stack([acq.traj for acq in acquisitions], axis=0)
        traj = trajdcf[..., :-1]
        dcf = trajdcf[..., -1]
    else:
        traj, dcf = None, None
    
    return data, traj, dcf


def _sort_data(data, traj, dcf, acquisitions, mrdhead):
    
    # order
    icontrast = np.asarray([acq.idx.contrast for acq in acquisitions])
    iz = np.asarray([acq.idx.slice for acq in acquisitions])
    iview = np.asarray([acq.idx.kspace_encode_step_1 for acq in acquisitions])
                
    # get geometry from header
    shape = mrdhead.encoding[0].encodingLimits
                
    # get sizes
    ncoils = data.shape[1]
    ncontrasts = shape.contrast.maximum+1
    nslices = shape.slice.maximum+1
    nviews = shape.kspace_encoding_step_1.maximum+1
    npts = data.shape[-1]
    ndims = traj.shape[-1] # last tims stores dcfs

    # get fov, matrix size and kspace size
    shape = (ncontrasts, nslices, nviews, npts)
    
    # sort trajectory, dcf and t
    datatmp = np.zeros([ncoils] + list(shape), dtype=np.complex64)
        
    if traj is not None:
        # preallocate
        trajtmp = np.zeros(list(shape) + [ndims], dtype=np.float32)
        dcftmp = np.zeros(shape, dtype=np.float32)
            
        # actual sorting
        _loop_sorting(datatmp, data, icontrast, iz, iview)
        _loop_sorting(trajtmp, traj, icontrast, iz, iview)
        _loop_sorting(dcftmp, dcf, icontrast, iz, iview)
           
        # assign
        data = np.ascontiguousarray(datatmp.squeeze())
        traj = np.ascontiguousarray(trajtmp.squeeze())
        dcf = np.ascontiguousarray(dcftmp.squeeze())
    else:
        # actual sorting
        _loop_sorting(datatmp, data, icontrast, iz, iview)

        # assign
        data = np.ascontiguousarray(datatmp.squeeze())
        
    # keep ordering
    ordering = np.stack((icontrast, iz, iview), axis=0)
        
    return data, traj, dcf, ordering


@nb.njit(cache=True)
def _loop_sorting(output, input, echo_num, slice_num, view_num):
    # get size
    nframes = input.shape[0]
    
    # actual reordering
    for n in range(nframes):
        iecho = echo_num[n]
        islice = slice_num[n]
        iview = view_num[n]
        output[:, iecho, islice, iview, :] = input[n]
        
    
