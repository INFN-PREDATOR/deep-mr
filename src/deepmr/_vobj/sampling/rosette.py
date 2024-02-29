"""Two-dimensional rosette sampling."""

__all__ = ["rosette"]

import math
import numpy as np

# this is for stupid Sphinx
try:
    from ... import _design
except Exception:
    pass

from ..._types import Header


def rosette(shape, nviews=None, bending_factor=1.0):
    r"""
    Design a rosette trajectory.

    The rosette petals are rotated by a pseudo golden angle
    with period 377 interelaves. Rotations are performed both along
    ``view`` and ``contrast`` dimensions. Acquisition is assumed to
    traverse the ``contrast`` dimension first and then the ``view``,
    i.e., all the contrasts are acquired before moving to the second view.
    If multiple echoes are specified, final contrast dimensions will have
    length ``ncontrasts * nechoes``.

    Parameters
    ----------
    shape : Iterable[int]
        Matrix shape ``(in-plane, contrasts=1, echoes=1)``.
    nviews : int, optional
        Number of spokes.
        The default is ``$\pi$ * shape`` if ``shape[1] == 1``, otherwise it is ``1``.
    bending_factor : float, optional
        This is ``0.0`` for radial-like trajectory; increase for maximum coverage per shot.
        In real world, must account for hardware and safety limitations.
        The default is ``1.0``.

    Returns
    -------
    head : Header
        Acquisition header corresponding to the generated sampling pattern.

    Example
    -------
    >>> import deepmr

    We can create a Nyquist-sampled rosette trajectory for an in-plane matrix of ``(128, 128)`` pixels by:

    >>> head = deepmr.rosette(128)

    An undersampled trajectory can be generated by specifying the ``nviews`` argument:

    >>> head = deepmr.rosette(128, nviews=64)
    
    Petals bending can be modified via ``bending_factor``:
        
    >>> head = deepmr.rosette(128, bending_factor=1.0) # radial-like trajectory

    Multiple contrasts with different sampling (e.g., for MR Fingerprinting) can be achieved by providing
    a tuple of ints as the ``shape`` argument:

    >>> head = deepmr.rosette((128, 420))
    >>> head.traj.shape
    torch.Size([420, 1, 128, 2])

    corresponding to 420 different contrasts, each sampled with a different single radial spoke of 128 points.
    Similarly, multiple echoes (with fixed sampling) can be specified as:

    >>> head = deepmr.rosette((128, 1, 8)) # 8 echoes
    >>> head.traj.shape
    torch.Size([8, 402, 128, 2])

    corresponding to a 8-echoes fully sampled k-spaces, e.g., for QSM and T2* mapping.

    Notes
    -----
    The returned ``head`` (:func:`deepmr.Header`) is a structure with the following fields:

    * shape (torch.Tensor):
        This is the expected image size of shape ``(nz, ny, nx)``.
    * t (torch.Tensor):
        This is the readout sampling time ``(0, t_read)`` in ``ms``.
        with shape ``(nsamples,)``.
    * traj (torch.Tensor):
        This is the k-space trajectory normalized as ``(-0.5 * shape, 0.5 * shape)``
        with shape ``(ncontrasts, nviews, nsamples, 2)``.
    * dcf (torch.Tensor):
        This is the k-space sampling density compensation factor
        with shape ``(ncontrasts, nviews, nsamples)``.
    * TE (torch.Tensor):
        This is the Echo Times array.

    """
    # expand shape if needed
    if np.isscalar(shape):
        shape = [shape, 1]
    else:
        shape = list(shape)

    while len(shape) < 3:
        shape = shape + [1]
        
    # default views
    if nviews is None:
        if shape[1] == 1:
            nviews = int(math.pi * shape[0])
        else:
            nviews = 1

    # assume 1mm iso
    fov = shape[0]
    
    # get number of contrasts
    ncontrasts = shape[1]
    shape[1] = 1
    shape = [shape[0], shape[2], shape[1]]

    # design single interleaf spiral
    tmp, _ = _design.rosette(fov, shape, 1, 1, int(math.pi * shape[0]), bending_factor)

    # generate angles
    dphi = (1 - 233 / 377) * 360.0
    phi = np.arange(ncontrasts * nviews) * dphi  # angles in degrees
    phi = np.deg2rad(phi)  # angles in radians

    # build rotation matrix
    rot = _design.angleaxis2rotmat(phi, "z")

    # get trajectory
    traj = tmp["kr"] * tmp["mtx"]
    traj = _design.projection(traj[0].T, rot)
    traj = traj.swapaxes(-2, -1).T
    traj = traj.reshape(nviews, ncontrasts, *traj.shape[-2:])
    traj = traj.swapaxes(0, 1)
    
    # expand echoes
    nechoes = shape[1]
    traj = np.repeat(traj, nechoes, axis=0)

    # get dcf
    dcf = tmp["dcf"]

    # get shape
    shape = tmp["mtx"]

    # get time
    t = tmp["t"]

    # calculate TE
    TE = tmp["te"]

    # get indexes
    head = Header(shape, t=t, traj=traj, dcf=dcf, TE=TE)
    head.torch()

    return head




