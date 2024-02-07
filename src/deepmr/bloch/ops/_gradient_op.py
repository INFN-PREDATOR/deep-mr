"""
EPG Gradient operators.

Can be used to simulate dephasing due spoiling gradient
and perfect crushing (i.e. after prep pulse or refocus pulse).
"""

__all__ = ["Shift", "Spoil"]

import torch

from ._abstract_op import Operator

class Shift(Operator):
    """
    Perform shift operator corrsesponding to a 2npi dephasing of the magnetization.

    Parameters
    ----------
    states : dict
        Input states matrix for free pools.


    Returns
    -------
    states : dict 
        Output states matrix for free pools.

    """

    def apply(self, states):
        """Apply states shifting."""
        # parse
        F = states["F"]

        # apply
        F[..., 0] = torch.roll(F[..., 0], 1, -3)  # Shift Fp states
        F[..., 1] = torch.roll(F[..., 1], -1, -3)  # Shift Fm states
        F[-1, ..., 1] = 0.0  # Zero highest Fm state
        F[0, ..., 0] = F[0, ..., 1].conj()  # Fill in lowest Fp state

        # prepare for output
        states["F"] = F
        return states


class Spoil(Operator):
    """
    Non-physical spoiling operator that zeros all transverse states.

    Parameters
    ----------
    states : dict
        Input states matrix for free pools.


    Returns
    -------
    states : dict 
        Output states matrix for free pools.
        
    """

    def apply(self, states):
        """Destroy transverse magnetization."""
        # parse
        F = states["F"]

        # apply
        F[..., 0] = 0.0
        F[..., 1] = 0.0

        # prepare for output
        states["F"] = F
        return states
