"""Three-dimensional stack-of-stars sampling."""

__all__ = ["radial_stack"]

import math
import numpy as np

# this is for stupid Sphinx
try:
    from ... import _design
except Exception:
    pass

from ..._types import Header


def radial_stack(shape, nviews=None, accel=1, **kwargs):
    r"""
    Design a stack-of-stars trajectory.

    As in the 2D radial case, spokes are rotated by a pseudo golden angle
    with period 377 interelaves. Rotations are performed both along
    ``view`` and ``contrast`` dimensions. Acquisition is assumed to
    traverse the ``contrast`` dimension first and then the ``view``,
    i.e., all the contrasts are acquired before moving to the second view.
    If multiple echoes are specified, final contrast dimensions will have
    length ``ncontrasts * nechoes``. Echoes are assumed to be acquired
    sequentially with the same spoke.

    Finally, slice dimension is assumed to be the outermost loop.

    Parameters
    ----------
    shape : Iterable[int]
        Matrix shape ``(in-plane, slices=1, contrasts=1, echoes=1)``.
    nviews : int, optional
        Number of spokes.
        The default is ``$\pi$ * shape[0]`` if ``shape[1] == 1``, otherwise it is ``1``.
    accel : int, optional
        Slice acceleration factor.
        Ranges from ``1`` (fully sampled) to ``nslices``.
        The default is ``1``.

    Keyword Arguments
    -----------------
    acs_shape : int
        Matrix size for inner (coil sensitivity estimation) region along slice encoding direction.
        The default is ``None``.
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

    We can create a Nyquist-sampled stack-of-stars trajectory for a ``(128, 128, 120)`` voxels matrix by:

    >>> head = deepmr.radial_stack((128, 120))

    An undersampled trajectory can be generated by specifying the ``nviews`` argument:

    >>> head = deepmr.radial_stack((128, 120), nviews=64)

    Slice acceleration can be specified using the ``accel`` argument. For example, the following

    >>> head = deepmr.radial_stack((128, 120), accel=2)

    will generate the following trajectory:

    >>> head.traj.shape
    torch.Size([1, 24120, 128, 3])

    i.e., a Nyquist-sampled stack-of-stars trajectory with a slice acceleration of 2 (i.e., 60 encodings).

    Parallel imaging calibration region can be specified using ``acs_shape`` argument:

    >>> head = deepmr.radial_stack((128, 120), accel=2, acs_shape=32)

    The generated stack will have an inner ``32``-wide fully sampled k-space region.

    Multiple contrasts with different sampling (e.g., for MR Fingerprinting) can be achieved by providing
    a tuple of ints as the ``shape`` argument:

    >>> head = deepmr.radial_stack((128, 120, 420))
    >>> head.traj.shape
    torch.Size([420, 120, 128, 3])

    corresponding to 420 different contrasts, each sampled with a single radial spoke of 128 points,
    repeated for 120 slice encodings. Similarly, multiple echoes (with fixed sampling) can be specified as:

    >>> head = deepmr.radial_stack((128, 120, 1, 8))
    >>> head.traj.shape
    torch.Size([8, 48240, 128, 3])

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
    assert len(shape) >= 2, "Please provide at least (in-plane, nslices) as shape."

    # expand shape if needed
    shape = list(shape)

    while len(shape) < 4:
        shape = shape + [1]

    # default views
    if nviews is None:
        if shape[2] == 1:
            nviews = int(math.pi * shape[0])
        else:
            nviews = 1

    # expand acs if needed
    if "acs_shape" in kwargs:
        acs_shape = kwargs["acs_shape"]
    else:
        acs_shape = None
    kwargs.pop("acs_shape", None)

    # assume 1mm iso
    fov = shape[0]

    # design single interleaf spiral
    tmp, _ = _design.radial(fov, shape[0], 1, 1, **kwargs)

    # rotate
    ncontrasts = shape[2]

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

    # expand slices
    nz = shape[1]
    az = np.arange(-nz // 2, nz // 2, dtype=np.float32)

    # accelerate
    az = az[::accel]

    # add back ACS
    if acs_shape is not None:
        az = np.concatenate(
            (az, np.arange(-acs_shape // 2, acs_shape // 2, dtype=np.float32))
        )
        az = np.unique(az)

    # expand
    traj = np.apply_along_axis(np.tile, -3, traj, len(az))
    az = np.repeat(az, nviews)
    az = az[None, :, None] * np.ones_like(traj[..., 0])

    # append new axis
    traj = np.concatenate((traj, az[..., None]), axis=-1)

    # expand echoes
    nechoes = shape[-1]
    traj = np.repeat(traj, nechoes, axis=0)

    # get dcf
    dcf = tmp["dcf"]

    # get shape
    shape = [shape[1]] + tmp["mtx"]

    # get time
    t = tmp["t"]

    # calculate TE
    min_te = float(tmp["te"][0])
    TE = np.arange(nechoes, dtype=np.float32) * t[-1] + min_te

    # extra args
    user = {}
    user["acs_shape"] = tmp["acs"]["mtx"]

    # get indexes
    head = Header(shape, t=t, traj=traj, dcf=dcf, TE=TE, user=user)
    head.torch()

    return head
