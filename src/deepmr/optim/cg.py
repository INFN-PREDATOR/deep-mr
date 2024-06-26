"""Conjugate Gradient iteration."""

__all__ = ["cg_solve", "CGStep"]

import time

import numpy as np
import torch

import torch.nn as nn

from .. import linops as _linops


@torch.no_grad()
def cg_solve(
    input,
    AHA,
    niter=10,
    device=None,
    tol=1e-4,
    lamda=0.0,
    ndim=None,
    save_history=False,
    verbose=False,
):
    """
    Solve inverse problem using Conjugate Gradient method.

    Parameters
    ----------
    input : np.ndarray | torch.Tensor
        Signal to be reconstructed. Assume it is the adjoint AH of measurement
        operator A applied to the measured data y (i.e., input = AHy).
    AHA : Callable | torch.Tensor | np.ndarray
        Normal operator AHA = AH * A.
    niter : int, optional
        Number of iterations. The default is ``10``.
    device : str, optional
        Computational device.
        The default is ``None`` (infer from input).
    tol : float, optional
        Stopping condition. The default is ``1e-4``.
    lamda : float, optional
        Tikhonov regularization strength. The default is ``0.0``.
    ndim : int, optional
        Number of spatial dimensions of the problem.
        It is used to infer the batch axes. If ``AHA`` is a ``deepmr.linop.Linop``
        operator, this is inferred from ``AHA.ndim`` and ``ndim`` is ignored.
    save_history : bool, optional
        Record cost function. The default is ``False``.
    verbose : bool, optional
        Display information. The default is ``False``.

    Returns
    -------
    output : np.ndarray | torch.Tensor
        Reconstructed signal.

    """
    # cast to numpy if required
    if isinstance(input, np.ndarray):
        isnumpy = True
        input = torch.as_tensor(input)
    else:
        isnumpy = False
        
    # assert inputs are correct
    if verbose:
        assert save_history is True, "We need to record history to print information."
        
    # keep original device
    idevice = input.device
    if device is None:
        device = idevice

    # put on device
    input = input.to(device)
    if isinstance(AHA, _linops.Linop):
        AHA = AHA.to(device)
    elif callable(AHA) is False:
        AHA = torch.as_tensor(AHA, dtype=input.dtype, device=device)

    # assume input is AH(y), i.e., adjoint of measurement operator
    # applied on measured data
    AHy = input.clone()

    # add Tikhonov regularization
    if lamda != 0.0:
        if isinstance(AHA, _linops.Linop):
            _AHA = AHA + lamda * _linops.Identity(AHA.ndim)
        elif callable(AHA):
            _AHA = lambda x: AHA(x) + lamda * x
        else:
            _AHA = lambda x: AHA @ x + lamda * x
    else:
        _AHA = AHA

    # initialize algorithm
    CG = CGStep(_AHA, AHy, ndim, tol)

    # initialize
    input = 0 * input
    history = []
    
    # start timer
    if verbose:
        t0 = time.time()
        nprint = np.linspace(0, niter, 5)
        nprint = nprint.astype(int).tolist()
        print("====================== Conjugate Gradient ==========================")
        print("| nsteps | data consistency | regularization | total cost | t-t0 [s]")
        print("====================================================================")
        
    # run algorithm
    for n in range(niter):
        output = CG(input)
        
        # if required, compute residual and check if we reached convergence
        if CG.check_convergence():
            break
        
        # update variable
        input = output.clone()
        
        # if required, save history
        if save_history:
            r = output - AHy
            dc = 0.5 * torch.linalg.norm(r).item() ** 2
            reg = lamda * torch.linalg.norm(output).item() ** 2
            history.append(dc+reg)
            if verbose and n in nprint:
                t = time.time()
                print(" {}{:.4f}{:.4f}{:.4f}{:.2f}".format(n, dc, reg, dc+reg, t-t0))
                
    if verbose:
        t1 = time.time()
        print(f"Exiting Conjugate Gradient: total elapsed time: {round(t1-t0, 2)} [s]")

    # back to original device
    output = output.to(device)

    # cast back to numpy if requried
    if isnumpy:
        output = output.numpy(force=True)

    return output, history


class CGStep(nn.Module):
    """
    Conjugate Gradient method step.

    This represents propagation through a single iteration of a
    CG algorithm; can be used to build
    unrolled architectures.

    Attributes
    ----------
    AHA : Callable | torch.Tensor
        Normal operator AHA = AH * A.
    Ahy : torch.Tensor
        Adjoint AH of measurement
        operator A applied to the measured data y.
    ndim : int
        Number of spatial dimensions of the problem.
        It is used to infer the batch axes. If ``AHA`` is a ``deepmr.linop.Linop``
        operator, this is inferred from ``AHA.ndim`` and ``ndim`` is ignored.
    tol : float, optional
        Stopping condition.
        The default is ``None`` (run until niter).

    """

    def __init__(self, AHA, AHy, ndim=None, tol=None):
        super().__init__()
        # set up problem dims
        try:
            self.ndim = AHA.ndim
        except Exception:
            self.ndim = ndim
            
        # assign operators
        self.AHA = AHA
        self.AHy = AHy

        # preallocate
        self.r = self.AHy.clone()
        self.p = self.r
        self.rsold = self.dot(self.r, self.r)
        self.rsnew = None
        self.tol = tol

    def dot(self, s1, s2):
        dot = s1.conj() * s2
        dot = dot.reshape(*s1.shape[: -self.ndim], -1).sum(axis=-1)
        if np.isscalar(dot) is False:
            for n in range(self.ndim):
                dot = dot[..., None]

        return dot

    def forward(self, input):
        AHAp = self.AHA(self.p)
        alpha = self.rsold / self.dot(self.p, AHAp)
        output = input + self.p * alpha
        self.r = self.r + AHAp * (-alpha)
        self.rsnew = torch.real(self.dot(self.r, self.r))
        self.p = self.r + self.p * (self.rsnew / self.rsold)
        self.rsold = self.rsnew

        return output

    def check_convergence(self):
        if self.tol is not None:
            if (self.rsnew.sqrt() < self.tol).all():
                return True
            else:
                return False
        else:
            return False
