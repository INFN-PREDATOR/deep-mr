"""Three-dimensional radial projection sampling."""

__all__ = ["radial_proj"]

import math
import numpy as np

# this is for stupid Sphinx
try:
    from ... import _design
except Exception:
    pass

from ..._types import Header


def radial_proj(shape, nviews=None, order="ga", **kwargs):
    r"""
    Design a 3D radial projectiontrajectory.

    The trajectory consists of a 2D radial trajectory, whose plane
    is rotated to cover the 3D k-space. In-plane rotations
    are sequential. Plane rotation types are specified
    via the ``order`` argument.

    Parameters
    ----------
    shape : Iterable[int]
        Matrix shape ``(in-plane, contrasts=1, echoes=1)``.
    nviews : int, optional
        Number of spokes (in-plane, radial).
        The default is ``$\pi$ * (shape[0], shape[1])`` if ``shape[2] == 1``,
        otherwise it is ``($\pi$ * shape[0], 1)``.
    order : str, optional
        Radial plane rotation type.
        These can be:

        * ``ga``: Pseudo golden angle variation of periodicity ``377``.
        * ``ga::multiaxis``: Pseudo golden angle, i.e., same as ``ga`` but views are repeated 3 times on orthogonal axes.
        * ``ga-sh``: Shuffled pseudo golden angle.
        * ``ga-sh::multiaxis``: Multiaxis shuffled pseudo golden angle, i.e., same as ``ga-sh`` but views are repeated 3 times on orthogonal axes.

        The default is ``ga``.

    Keyword Arguments
    -----------------
    variant : str
        Type of radial trajectory. Allowed values are:

        * ``fullspoke``: starts at the edge of k-space and ends on the opposite side (default).
        * ``center-out``: starts at the center of k-space and ends at the edge.

    Returns
    -------
    head : Header
        Acquisition header corresponding to the generated sampling pattern.

    Example
    -------
    >>> import deepmr

    We can create a Nyquist-sampled 3D radial trajectory for a matrix of ``(128, 128, 128)`` voxels by:

    >>> head = deepmr.radial_proj(128)

    An undersampled trajectory can be generated by specifying the ``nviews`` argument:

    >>> head = deepmr.radial_proj(128, nviews=64)

    Multiple contrasts with different sampling (e.g., for MR Fingerprinting) can be achieved by providing
    a tuple of ints as the ``shape`` argument:

    >>> head = deepmr.radial_proj((128, 420))
    >>> head.traj.shape
    torch.Size([420, 402, 128, 2])

    corresponding to 420 different contrasts, each sampled with a different fully sampled plane.
    Similarly, multiple echoes (with fixed sampling) can be specified as:

    >>> head = deepmr.radial_proj((128, 1, 8))
    >>> head.traj.shape
    torch.Size([8, 161604, 128, 2])

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
        This is the Echo Times array. Assumes a k-space raster time of ``1 us``
        and minimal echo spacing.

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

    # expand nviews if needed
    if np.isscalar(nviews):
        nviews = [int(math.pi * shape[0]), nviews]
    else:
        nviews = list(nviews)

    # assume 1mm iso
    fov = shape[0]

    # design single interleaf spiral
    tmp, _ = _design.radial(fov, shape[0], 1, 1, **kwargs)

    # generate angles
    ncontrasts = shape[1]

    dphi = 360.0 / nviews[0]
    dtheta = (1 - 233 / 377) * 360.0

    # build rotation angles
    j = np.arange(ncontrasts * nviews[1])
    i = np.arange(nviews[0])

    j = np.tile(j, nviews[0])
    i = np.repeat(i, ncontrasts * nviews[1])

    # radial angle
    if order[:5] == "ga-sh":
        theta = (i + j) * dtheta
    else:
        theta = j * dtheta

    # in-plane angle
    phi = i * dphi

    # convert to radians
    theta = np.deg2rad(theta)  # angles in radians
    phi = np.deg2rad(phi)  # angles in radians

    # perform rotation
    axis = np.zeros_like(theta, dtype=int)  # rotation axis
    Rx = _design.angleaxis2rotmat(theta, [1, 0, 0])  # whole-plane rotation about x
    Rz = _design.angleaxis2rotmat(phi, [0, 0, 1])  # in-plane rotation about z

    # put together full rotation matrix
    rot = np.einsum("...ij,...jk->...ik", Rx, Rz)

    # get trajectory
    traj = tmp["kr"] * tmp["mtx"]
    traj = np.concatenate((traj, 0 * traj[..., [0]]), axis=-1)
    traj = _design.projection(traj[0].T, rot)
    traj = traj.swapaxes(-2, -1).T
    traj = traj.reshape(nviews[0], nviews[1], ncontrasts, *traj.shape[-2:])
    traj = traj.transpose(2, 1, 0, *np.arange(3, len(traj.shape)))
    traj = traj.reshape(ncontrasts, -1, *traj.shape[3:])

    # get dcf
    dcf = tmp["dcf"]
    dcf = _design.angular_compensation(dcf, traj.reshape(-1, *traj.shape[-2:]), axis)
    dcf = dcf.reshape(*traj.shape[:-1])

    # apply multiaxis
    if order[-9:] == "multiaxis":
        # expand trajectory
        traj1 = np.stack((traj[..., 2], traj[..., 0], traj[..., 1]), axis=-1)
        traj2 = np.stack((traj[..., 1], traj[..., 2], traj[..., 0]), axis=-1)
        traj = np.concatenate((traj, traj1, traj2), axis=-3)

        # expand dcf
        dcf = np.concatenate((dcf, dcf, dcf), axis=-2)

        # renormalize dcf
        tabs = (traj[0, 0] ** 2).sum(axis=-1) ** 0.5
        k0_idx = np.argmin(tabs)
        nshots = nviews[0] * nviews[1] * ncontrasts

        # impose that center of k-space weight is 1 / nshots
        scale = 1.0 / (dcf[[k0_idx]] + 0.000001) / nshots
        dcf = scale * dcf

    # expand echoes
    nechoes = shape[-1]
    traj = np.repeat(traj, nechoes, axis=0)
    dcf = np.repeat(dcf, nechoes, axis=0)

    # get shape
    shape = [shape[0]] + list(tmp["mtx"])

    # get time
    t = tmp["t"]

    # calculate TE
    min_te = float(tmp["te"][0])
    TE = np.arange(nechoes, dtype=np.float32) * t[-1] + min_te

    # get indexes
    head = Header(shape, t=t, traj=traj, dcf=dcf, TE=TE)
    head.torch()

    return head
