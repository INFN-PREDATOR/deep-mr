"""KSpace IO routines."""

import math
import time

import numpy as np
import torch

from . import gehc as _gehc
from . import mrd as _mrd
# from . import siemens as _siemens

__all__ = ["read_rawdata"]

def read_rawdata(filepath, acqheader=None, device="cpu", verbose=0):
    """
    Read kspace data from file.

    Parameters
    ----------
    filepath : str
        Path to kspace file.
    acqheader : Header, deepmr.optional
        Acquisition header loaded from trajectory.
        If not provided, assume Cartesian acquisition and infer from data.
        The default is None.
    device : str, optional
        Computational device for internal attributes. The default is "cpu".
    verbose : int, optional
        Verbosity level (0=Silent, 1=Less, 2=More). The default is 0.
    
    Returns
    -------
    data : torch.tensor
        Complex k-space data of shape (nslices, ncoils, ncontrasts, nviews, nsamples).
    head : deepmr.Header
        Metadata for image reconstruction.
    """
    tstart = time.time()
    if verbose >= 1:
        print(f"Reading raw k-space from file {filepath}...", end="\t")
        
    done = False
    
    # convert header to numpy
    if acqheader is not None:
        acqheader.numpy()

    # mrd
    if verbose == 2:
        t0 = time.time()
    try:            
        data, head = _mrd.read_mrd_rawdata(filepath)
        done = True
    except Exception:
        pass
    
    # gehc
    if not(done):
        try:
            data, head = _gehc.read_gehc_rawdata(filepath, acqheader)
            done = True
        except Exception:
            pass
     
    # siemens
    # if not(done):
    #     try:
    #         head = _siemens.read_siemens_rawdata(filepath, acqheader)
    #         done = True
    #     except Exception:
    #         pass

    # check if we loaded data
    if not(done):
        raise RuntimeError(f"File (={filepath}) not recognized!")
    if verbose == 2:
        t1 = time.time()
        print(f"done! Elapsed time: {round(t1-t0, 2)} s")
        
    # transpose
    data = data.transpose(2, 0, 1, 3, 4) # (slice, coil, contrast, view, sample)  
    
    # select actual readout
    if verbose == 2:
        nsamples = data.shape[-1]
        print("Selecting actual readout samples...", end="\t")
        t0 = time.time()
    data = _select_readout(data, head)
    if verbose == 2:
        t1 = time.time()
        print(f"done! Selected {data.shape[-1]} out of {nsamples} samples. Elapsed time: {round(t1-t0, 2)} s")

    # center fov
    if verbose == 2:
        if head.traj is not None:
            t0 = time.time()
            ndim = head.traj.shape[-1]
            shift = head._shift[:ndim]
            if ndim == 2:
                print(f"Shifting FoV by (dx={shift[0]}, dy={shift[1]}) mm", end="\t")
            if ndim == 3:
                print(f"Shifting FoV by (dx={shift[0]}, dy={shift[1]}, dz={shift[2]}) mm", end="\t")
    data = _fov_centering(data, head)
    if verbose == 2:
        if head.traj is not None:
            t1 = time.time()
            print(f"done! Elapsed time: {round(t1-t0, 2)} s")
    
    # remove oversampling for Cartesian
    if "mode" in head.user:
        if head.user["mode"][2:] == "cart":
            if verbose == 2:
                t0 = time.time()
                ns1 = data.shape[0]
                ns2 = head.shape[0]
                print(f"Removing oversampling along readout ({round(ns1/ns2, 2)})...", end="\t")
            data, head = _remove_oversampling(data, head)
            if verbose == 2:
                t1 = time.time()
                print(f"done! Elapsed time: {round(t1-t0, 2)} s")
    
    # transpose readout in slice direction for 3D Cartesian
    if "mode" in head.user:
        if head.user["mode"] == "3Dcart":
            data = data.transpose(-1, 1, 2, 0, 3) # (z, ch, e, y, x) -> (x, ch, e, z, y)
            
    # decouple separable acquisition
    if "separable" in head.user and head.user["separable"]:
        if verbose == 2:
            t0 = time.time()
            print("Separable 3D acquisition, performing FFT along slice...", end="\t")
        data = _fft(data, 0)
        if verbose == 2:
            t1 = time.time()
            print(f"done! Elapsed time: {round(t1-t0, 4)} s")
        
    # set-up transposition
    if "mode" in head.user:
        if head.user["mode"] == "2Dcart":
            head.transpose = [1, 0, 2, 3]
            if verbose == 2:
                print("Acquisition mode: 2D Cartesian")
                print(f"K-space shape: (nslices={data.shape[0]}, nchannels={data.shape[1]}, ncontrasts={data.shape[2]}, ny={data.shape[3]}, nx={data.shape[4]})")
                print(f"Expected image shape: (nslices={data.shape[0]}, nchannels={data.shape[1]}, ncontrasts={data.shape[2]}, ny={head.shape[1]}, nx={head.shape[2]})")
        elif head.user["mode"] == "2Dnoncart":
            head.transpose = [1, 0, 2, 3]
            if verbose == 2:
                print("Acquisition mode: 2D Non-Cartesian")
                print(f"K-space shape: (nslices={data.shape[0]}, nchannels={data.shape[1]}, ncontrasts={data.shape[2]}, nviews={data.shape[3]}, nsamples={data.shape[4]})")
                print(f"Expected image shape: (nslices={data.shape[0]}, nchannels={data.shape[0]}, ncontrasts={data.shape[1]}, ny={head.shape[1]}, nx={head.shape[2]})")
        elif head.user["mode"] == "3Dnoncart":
            data = data[0]
            head.transpose = [1, 0, 2, 3]
            if verbose == 2:
                print("Acquisition mode: 3D Non-Cartesian")
                print(f"K-space shape: (nchannels={data.shape[0]}, ncontrasts={data.shape[1]}, nviews={data.shape[2]}, nsamples={data.shape[3]})")
                print(f"Expected image shape: (nchannels={data.shape[0]}, ncontrasts={data.shape[1]}, nz={head.shape[0]}, ny={head.shape[1]}, nx={head.shape[2]})")
        elif head.user["mode"] == "3Dcart":
            head.transpose = [1, 2, 3, 0]
            if verbose == 2:
                print("Acquisition mode: 3D Cartesian")
                print(f"K-space shape: (nx={data.shape[0]}, nchannels={data.shape[1]}, ncontrasts={data.shape[2]}, nz={data.shape[3]}, ny={data.shape[4]})")
                print(f"Expected image shape: (nx={head.shape[2]}, nchannels={data.shape[1]}, ncontrasts={data.shape[2]}, nz={head.shape[0]}, ny={head.shape[1]})")
        
        # remove unused trajectory for cartesian
        if head.user["mode"][2:] == "cart":
            head.traj = None
            head.dcf = None
            
    # clean header
    head.user.pop("mode", None)
    head.user.pop("separable", None)
    
    # final report
    if verbose == 2:
        print(f"Readout time: {round(float(head.t[-1]), 2)} ms")
        if head.traj is not None:
            print(f"Trajectory shape: (ncontrasts={head.traj.shape[0]}, nviews={head.traj.shape[1]}, nsamples={head.traj.shape[2]}, ndim={head.traj.shape[-1]})")      
        if head.dcf is not None:
            print(f"DCF shape: (ncontrasts={head.dcf.shape[0]}, nviews={head.dcf.shape[1]}, nsamples={head.dcf.shape[2]})")
        if head.FA is not None:
            if len(np.unique(head.FA)) > 1:
                print(f"Flip Angle train length: {len(head.FA)}")
            else:
                FA = float(np.unique(head.FA)[0])
                print(f"Constant FA: {round(abs(FA), 2)} deg")
        if head.TR is not None:
            if len(np.unique(head.TR)) > 1:
                print(f"TR train length: {len(head.TR)}")
            else:
                TR = float(np.unique(head.TR)[0])
                print(f"Constant TR: {round(TR, 2)} ms")
        if head.TE is not None:
            if len(np.unique(head.TE)) > 1:
                print(f"Echo train length: {len(head.TE)}")
            else:
                TE = float(np.unique(head.TE)[0])
                print(f"Constant TE: {round(TE, 2)} ms")
        if head.TI is not None and np.allclose(head.TI, 0.0) is False:
            if len(np.unique(head.TI)) > 1:
                print(f"Inversion train length: {len(head.TI)}")
            else:
                TI = float(np.unique(head.TI)[0])
                print(f"Constant TI: {round(TI, 2)} ms")
          
    # cast
    data = torch.as_tensor(np.ascontiguousarray(data), dtype=torch.complex64, device=device)
    head.torch(device)
    
    tend = time.time()
    if verbose == 1:
        print(f"done! Elapsed time: {round(tend-tstart, 2)} s")
    elif verbose == 2:
        print(f"Total elapsed time: {round(tend-tstart, 2)} s")

    return data, head

# %% sub routines
def _select_readout(data, head):
    if head._adc is not None:
        if head._adc[-1] == data.shape[-1]:
            data = data[..., head._adc[0]:]
        else:
            data = data[..., head._adc[0]:head._adc[1]+1]
    return data
    
def _fov_centering(data, head):
    
    if head.traj is not None and np.allclose(head._shift, 0.0) is False:
        
        # ndimensions
        ndim = head.traj.shape[-1]
        
        # shift (mm)
        dr = np.asarray(head._shift)[:ndim]
        
        # convert in units of voxels
        dr /= head._resolution[::-1][:ndim]
        
        # apply
        data *= np.exp(1j * 2 * math.pi * (head.traj * dr).sum(axis=-1))
        
    return data

def _remove_oversampling(data, head):
    if data.shape[-1] != head.shape[-1]: # oversampled
        center = int(data.shape[-1] // 2)
        hwidth = int(head.shape[-1] // 2)
        data = _fft(data, -1)
        data = data[..., center-hwidth:center+hwidth]
        data = _fft(data, -1)
        dt = np.diff(head.t)[0]
        head.t = np.linspace(0, head.t[-1], data.shape[-1])
    
    return data, head

def _fft(data, axis):
    tmp = torch.as_tensor(data)
    tmp = torch.fft.fftshift(torch.fft.fft(torch.fft.fftshift(tmp, dim=axis), dim=axis), dim=axis)
    return tmp.numpy()