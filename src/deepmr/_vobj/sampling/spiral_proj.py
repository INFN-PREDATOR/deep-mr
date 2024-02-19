"""Three-dimensional spiral projection sampling."""

__all__ = ["spiral_proj"]

import numpy as np

# this is for stupid Sphinx
try:
    from ... import _design
except Exception:
    pass

from ..._types import Header


def spiral_proj(shape, accel=1, nintl=1, order="ga", **kwargs):
    r"""
    Design a constant- or multi-density spiral projection.
    
    The trajectory consists of a 2D spiral, whose plane
    is rotated to cover the 3D k-space. In-plane rotations
    are sequential. Plane rotation types are specified
    via the ``order`` argument.

    Parameters
    ----------
    shape : Iterable[int]
        Matrix shape ``(in-plane, contrasts=1, echoes=1)``.
    accel : int, optional
        In-plane acceleration. Ranges from ``1`` (fully sampled) to ``nintl``.
        The default is ``1``.
    nintl : int, optional
        Number of interleaves to fully sample a plane.
        The default is ``1``.
    order : str, optional
        Spiral plane rotation type. 
        These can be:
            
        * ``ga``: Pseudo golden angle variation of periodicity ``377``.
        * ``ga::multiaxis``: Pseudo golden angle, i.e., same as ``ga`` but views are repeated 3 times on orthogonal axes.
        * ``ga-sh``: Shuffled pseudo golden angle.
        * ``ga-sh::multiaxis``: Multiaxis shuffled pseudo golden angle, i.e., same as ``ga-sh`` but views are repeated 3 times on orthogonal axes.
            
        The default is ``ga``.

    Keyword Arguments
    -----------------
    moco_shape : int
        Matrix size for inner-most (motion navigation) spiral.
        The default is ``None``.
    acs_shape : int
        Matrix size for intermediate inner (coil sensitivity estimation) spiral.
        The default is ``None``.
    acs_nintl : int
        Number of interleaves to fully sample intermediate inner spiral.
        The default is ``1``.
    variant : str
        Type of spiral. Allowed values are:

        * ``center-out``: starts at the center of k-space and ends at the edge (default).
        * ``reverse``: starts at the edge of k-space and ends at the center.
        * ``in-out``: starts at the edge of k-space and ends on the opposite side (two 180° rotated arms back-to-back).

    Returns
    -------
    head : Header
        Acquisition header corresponding to the generated spiral.

    Example
    -------
    >>> import deepmr

    We can create a single-shot spiral projection for an in-plane matrix of ``(128, 128, 128)`` pixels by:

    >>> head = deepmr.spiral_proj(128)

    An in-plane multi-shot trajectory can be generated by specifying the ``nintl`` argument:

    >>> head = deepmr.spiral_proj(128, nintl=48)

    Both spirals have constant density. If we want a dual density we can use ``acs_shape`` and ``acs_nintl`` arguments.
    For example, if we want an inner ``(32, 32)`` k-space region sampled with a 4 interleaves spiral, this can be obtained as:

    >>> head = deepmr.spiral_proj(128, nintl=48, acs_shape=32, acs_nintl=4)

    This inner region can be used e.g., for Parallel Imaging calibration. Similarly, a triple density spiral can
    be obtained by using the ``moco_shape`` argument:

    >>> head = deepmr.spiral_proj(128, nintl=48, acs_shape=32, acs_nintl=4, moco_shape=8)

    The generated spiral will have an innermost ``(8, 8)`` single-shot k-space region (e.g., for PROPELLER-like motion correction),
    an intermediate ``(32, 32)`` k-space region fully covered by 4 spiral shots and an outer ``(128, 128)`` region fully covered by 48 interleaves.

    In-plane acceleration can be specified using the ``accel`` argument. For example, the following

    >>> head = deepmr.spiral_proj(128, nintl=48, accel=4)

    will generate the following trajectory:

    >>> head.traj.shape
    torch.Size([1, 1536, 538, 2])

    i.e., a 48-interleaves trajectory with an in-plane acceleration factor of 4 (i.e., 12 interleaves),
    repeated for 128 planes covering the 3D k-space sphere.

    Multiple contrasts with different sampling (e.g., for MR Fingerprinting) can be achieved by providing
    a tuple of ints as the ``shape`` argument:

    >>> head = deepmr.spiral_proj((128, 420), nintl=48)
    >>> head.traj.shape
    torch.Size([420, 48, 538, 2])

    corresponding to 420 different contrasts, each sampled with a different fully sampled plane.
    Similarly, multiple echoes (with fixed sampling) can be specified as:

    >>> head = deepmr.spiral_proj((128, 1, 8), nintl=48)
    >>> head.traj.shape
    torch.Size([8, 6144, 538, 2])

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
        with shape ``(ncontrasts, nviews, nsamples, 3)``.
    * dcf (torch.Tensor):
        This is the k-space sampling density compensation factor
        with shape ``(ncontrasts, nviews, nsamples)``.

    """
    # expand shape if needed
    if np.isscalar(shape):
        shape = [shape, 1]
    else:
        shape = list(shape)

    while len(shape) < 3:
        shape = shape + [1]
        
    # assume 1mm iso
    fov = shape[0]

    # design single interleaf spiral
    tmp, _ = _design.spiral(fov, shape[0], 1, nintl, **kwargs)

    # generate angles
    ncontrasts = shape[1]
    nviews = max(int(nintl // accel), 1)
    
    dphi = 360.0 / nintl
    dtheta = (1 - 233 / 377) * 360.0
    
    if ncontrasts == 1:
        j = np.arange(shape[0])
        i = np.arange(nviews)
        
        j = np.tile(j, nviews)
        i = np.repeat(i, shape[0])
        
        nviews = len(i)
    else:
        j = np.arange(ncontrasts)
        i = np.arange(nviews)
        
        j = np.tile(j, nviews)
        i = np.repeat(i, ncontrasts)
      
    if order[:5] == "ga-sh":
        theta = (i + j) * dtheta
    else:
        theta = j * dtheta
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
    traj = traj.reshape(nviews, ncontrasts, *traj.shape[-2:])
    traj = traj.swapaxes(0, 1)
    
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
        nshots = nviews * ncontrasts
        
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

    # extra args
    user = {}
    user["moco_shape"] = tmp["moco"]["mtx"]
    user["acs_shape"] = tmp["acs"]["mtx"]

    # get indexes
    head = Header(shape, t=t, traj=traj, dcf=dcf, TE=TE, user=user)
    head.torch()

    return head
