"""
Sub-package containing virtual objects generation routines.

DeepMR contains tools to simulate MR experiments for development and testing.
These tools include numerical phantoms, B0 and B1+ field generators,
random rigid motion generation routines and sampling trajectories (Cartesian and Non-Cartesian).

"""

__all__ = ["shepp_logan", "custom_phantom"]

import numpy as np
import torch

# from .brainweb import create_brainweb
from .ct_shepp_logan import ct_shepp_logan
from .mr_shepp_logan import mr_shepp_logan

def shepp_logan(npix, nslices=1, qmr=False, B0=3.0):
    """
    Initialize numerical phantom for MR simulations.

    This function generates a numerical phantom for qMR or MR simulations based on the provided parameters.

    Parameters
    ----------
    npix : Iterable[int]
        In-plane matrix size.
    nslices : int, optional
        Number of slices. An isotropic [npix, npix, npix] phantom can be
        generated, for convenience, by setting nslices to "-1". The default is "1".
    qmr : bool, optional
        Flag indicating whether the phantom is for qMRI (True) or MR (False) simulations. 
        The default is False.
    B0 : float, optional
        Static field strength in T. Ignored if `mr` is False.
        The default is 3.0.

    Returns
    -------
    phantom : torch.Tensor, dict
        Shepp-Logan phantom of shape (nslices, ny, nx) (qmr == False) or
        a dictionary of maps ("M0", "T1", "T2", "T2star", "chi") of 
        shape (nslices, ny, nx) (qmr == True).
        
    Examples
    --------
    >>> import deepmr
    
    We can generate a non-quantitative Shepp-Logan phantom as:
    
    >>> phantom = deepmr.shepp_logan(128)
    >>> phantom.shape
    torch.Size([128, 128])
    
    We also support multiple slices:
        
    >>> phantom = deepmr.shepp_logan(128, 32)
    >>> phantom.shape
    torch.Size([32, 128, 128])
    
    An isotropic [npix, npix, npix] phantom can be generated by setting nslices to "-1":
        
    >>> phantom = deepmr.shepp_logan(128, -1)
    >>> phantom.shape
    torch.Size([128, 128, 128])
    
    We can also generate quantitative M0, T1, T2, T2* and magnetic susceptibility maps:
        
    >>> phantom = deepmr.shepp_logan(128, qmr=True)
    >>> phantom.keys()
    dict_keys(['M0', 'T1', 'T2', 'T2star', 'chi'])
    
    Each map will have (nslices, npix, npix) shape:
    
    >>> phantom["M0"].shape
    torch.Size([128, 128])

    """
    if nslices < 0:
        nslices = npix
    if qmr:
        seg, mrtp, emtp = mr_shepp_logan(npix, nslices, B0)
        # - seg (tensor): phantom segmentation (e.g., 1 := GM, 2 := WM, 3 := CSF...)
        # - mrtp (list): list of dictionaries containing 1) free water T1/T2/T2*/ADC/v, 2) bm/mt T1/T2/fraction, 3) exchange matrix
        #          for each class (index along the list correspond to value in segmentation mask)
        # - emtp (list): list of dictionaries containing electromagnetic tissue properties for each class.
        
        # only support single model for now:
        prop = {"M0": mrtp["M0"], "T1": mrtp["T1"], "T2": mrtp["T2"], "T2star": mrtp["T2star"], "chi": emtp["chi"]}
        return custom_phantom(seg, prop)                                                                                   
    else:
        return ct_shepp_logan(npix, nslices)

def custom_phantom(segmentation, properties):
    """
    Initialize numerical phantom for MR simulations from user-provided segmentation.

    This function generates a numerical phantom for qMR simulations based on the segmentation and parameters.

    Parameters
    ----------
    segmentation : torch.Tensor
        Hard (i.e. non probabilistic) segmentation of the object of shape (nslices, ny, nx).
    properties : dict
        Dictionary with the properties for each class (e.g., properties.keys() =dict_keys(["M0", "T1", "T2", "T2star", "chi"])).
        Each property is a list, whose entries ordering should match the label values in "segmentation".
        For example, properties["T1"][2] is the T1 value of the region corresponding to (segmentation == 2).

    Returns
    -------
    phantom : dict
        Dictionary of maps (e.g., "M0", "T1", "T2", "T2star", "chi") of 
        shape (nslices, ny, nx).
        
    Examples
    --------
    >>> import torch
    >>> import deepmr
    
    We can initialize a simple tissue segmentation and its M0, T1 and T2 properties:
        
    >>> segmentation = torch.tensor([0, 0, 0, 1, 1, 1], dtype=int)
    >>> properties = {"M0": [0.7, 0.8], "T1": [500.0, 1000.0], "T2": [50.0, 100.0]}
    
    Now, we can use "create_phantom" to generate our M0, T1 and T2 maps:
        
    >>> phantom = deepmr.custom_phantom(segmentation, properties)
    >>> phantom["M0"]
    tensor([ 0.7, 0.7, 0.7, 0.8, 0.8, 0.8])
    >>> phantom["T1"]
    tensor([ 500., 500., 500., 1000., 1000., 1000.])
    >>> phantom["T2"]
    tensor([ 50., 50., 50., 100., 100., 100.])

    """
    assert np.issubdtype(segmentation.detach().cpu().numpy().dtype, np.floating) is False, "We only support hard segmentation right now."
    map_template = torch.zeros(segmentation.shape, dtype=torch.float32)
    labels = np.unique(segmentation)
    
    phantom = {}
    for key in properties.keys():
        value = map_template.clone()
        for idx in labels:
            value[segmentation == idx] = properties[key][idx]
        phantom[key] = value
        
    return phantom
        
# @_dataclass
# class ArbitraryPhantomBuilder:
#     """Helper class to build qMRI phantoms from externally provided maps."""

#     # relaxation properties
#     T1: _Union[float, _npt.NDArray]  # ms
#     T2: _Union[float, _npt.NDArray]  # ms
#     segmentation: _npt.NDArray = None
#     M0: float = 1.0

#     # other properties
#     T2star: _Union[float, _npt.NDArray] = 0.0  # ms
#     chemshift: _Union[float, _npt.NDArray] = 0.0  # Hz / T

#     # motion properties
#     D: _Union[float, _npt.NDArray] = 0.0  # um**2 / ms
#     v: _Union[float, _npt.NDArray] = 0.0  # cm / s

#     # multi-component related properties
#     exchange_rate: _Union[float, _npt.NDArray] = 0.0  # 1 / s

#     # smaller pools
#     bm: dict = None
#     mt: dict = None

#     # electromagnetic properties
#     chi: float = 0.0
#     sigma: float = 0.0  # S / m
#     epsilon: float = 0.0

#     # size and shape
#     n_atoms: int = 1
#     shape: tuple = None

#     def __post_init__(self):
#         # convert scalar to array and gather sizes and shapes
#         sizes = []
#         shapes = []
#         for field in _fields(self):
#             value = getattr(self, field.name)
#             if (
#                 field.name != "bm"
#                 and field.name != "mt"
#                 and field.name != "segmentation"
#                 and field.name != "n_atoms"
#                 and field.name != "shape"
#                 and field.name != "exchange_rate"
#             ):
#                 val = _np.asarray(value)
#                 sizes.append(val.size)
#                 shapes.append(val.shape)
#                 setattr(self, field.name, val)

#         # get number of atoms
#         self.n_atoms = _np.max(sizes)
#         self.shape = shapes[_np.argmax(sizes)]

#         # check shapes
#         shapes = [shape for shape in shapes if shape != ()]
#         assert (
#             len(set(shapes)) <= 1
#         ), "Error! All input valus must be either scalars or arrays of the same shape!"

#         # check segmentation consistence
#         if self.segmentation is not None:
#             seg = self.segmentation
#             if issubclass(seg.dtype.type, _np.integer):  # discrete segmentation case
#                 assert seg.max() == self.n_atoms - 1, (
#                     f"Error! Number of atoms = {self.n_atoms} must match number of"
#                     f" classes = {seg.max()}"
#                 )
#             else:
#                 assert seg.shape[0] == self.n_atoms - 1, (
#                     f"Error! Number of atoms = {self.n_atoms} must match number of"
#                     f" classes = {seg.shape[0]}"
#                 )

#         # expand scalars
#         for field in _fields(self):
#             value = getattr(self, field.name)
#             if (
#                 field.name != "bm"
#                 and field.name != "mt"
#                 and field.name != "segmentation"
#                 and field.name != "n_atoms"
#                 and field.name != "shape"
#                 and field.name != "exchange_rate"
#             ):
#                 if value.size == 1:
#                     value = value * _np.ones(self.shape, dtype=_np.float32)
#                 value = _np.atleast_1d(value)
#                 setattr(self, field.name, value)

#         # initialize exchange_rate
#         self.exchange_rate = _np.zeros(list(self.shape) + [1], dtype=_np.float32)

#         # initialize BM and MT pools
#         self.bm = {}
#         self.mt = {}

#     def add_cest_pool(
#         self,
#         T1: _Union[float, _npt.NDArray],
#         T2: _Union[float, _npt.NDArray],
#         weight: _Union[float, _npt.NDArray],
#         chemshift: _Union[float, _npt.NDArray] = 0.0,
#     ):
#         """
#         Add a new Chemical Exchanging pool to the model.

#         Args:
#             T1 (Union[float, npt.NDArray]): New pool T1.
#             T2 (Union[float, npt.NDArray]): New pool T2.
#             weight (Union[float, npt.NDArray]): New pool relative fraction.
#             chemshift (Union[float, npt.NDArray], optional): New pool chemical shift. Defaults to 0.0.

#         """
#         # check pool
#         if _np.isscalar(T1):
#             T1 *= _np.ones((self.n_atoms, 1), dtype=_np.float32)
#         elif len(T1.shape) == 1:
#             assert _np.array_equal(
#                 T1.shape, self.shape
#             ), "Input T1 must be either a scalar or match the existing shape."
#             T1 = T1[..., None]
#         else:
#             assert _np.array_equal(
#                 T1.squeeze().shape, self.shape
#             ), "Input T1 must be either a scalar or match the existing shape."
#             assert T1.shape[-1] == 1, "Pool dimension size must be 1!"
#         if _np.isscalar(T2):
#             T2 *= _np.ones((self.n_atoms, 1), dtype=_np.float32)
#         elif len(T2.shape) == 1:
#             assert _np.array_equal(
#                 T2.shape, self.shape
#             ), "Input T2 must be either a scalar or match the existing shape."
#             T2 = T2[..., None]
#         else:
#             assert _np.array_equal(
#                 T2.squeeze().shape, self.shape
#             ), "Input T2 must be either a scalar or match the existing shape."
#             assert T2.shape[-1] == 1, "Pool dimension size must be 1!"
#         if _np.isscalar(weight):
#             weight *= _np.ones((self.n_atoms, 1), dtype=_np.float32)
#         elif len(weight.shape) == 1:
#             assert _np.array_equal(
#                 weight.shape, self.shape
#             ), "Input weight must be either a scalar or match the existing shape."
#             weight = weight[..., None]
#         else:
#             assert _np.array_equal(
#                 weight.squeeze().shape, self.shape
#             ), "Input weight must be either a scalar or match the existing shape."
#             assert weight.shape[-1] == 1, "Pool dimension size must be 1!"
#         if _np.isscalar(chemshift):
#             chemshift *= _np.ones((self.n_atoms, 1), dtype=_np.float32)
#         elif len(chemshift.shape) == 1:
#             assert _np.array_equal(chemshift.shape, self.shape), (
#                 "Input chemical_shift must be either a scalar or match the existing"
#                 " shape."
#             )
#             chemshift = chemshift[..., None]
#         else:
#             assert _np.array_equal(chemshift.squeeze().shape, self.shape), (
#                 "Input chemical_shift must be either a scalar or match the existing"
#                 " shape."
#             )
#             assert chemshift.shape[-1] == 1, "Pool dimension size must be 1!"

#         # BM pool already existing; add a new component
#         if self.bm:
#             self.bm["T1"] = _np.concatenate((self.bm["T1"], T1), axis=-1)
#             self.bm["T2"] = _np.concatenate((self.bm["T2"], T2), axis=-1)
#             self.bm["weight"] = _np.concatenate((self.bm["weight"], weight), axis=-1)
#             self.bm["chemshift"] = _np.concatenate(
#                 (self.bm["chemshift"], chemshift), axis=-1
#             )
#         else:
#             self.bm["T1"] = T1
#             self.bm["T2"] = T2
#             self.bm["weight"] = weight
#             self.bm["chemshift"] = chemshift

#     def add_mt_pool(self, weight: _Union[float, _npt.NDArray]):
#         """
#         Set macromolecolar pool.

#         Args:
#             weight (Union[float, npt.NDArray]): Semisolid pool relative fraction.
#         """
#         # check pool
#         if _np.isscalar(weight):
#             weight *= _np.ones((self.n_atoms, 1), dtype=_np.float32)
#         elif len(weight.shape) == 1:
#             assert _np.array_equal(
#                 weight.shape, self.shape
#             ), "Input weight must be either a scalar or match the existing shape."
#             weight = weight[..., None]
#         else:
#             assert _np.array_equal(
#                 weight.squeeze().shape, self.shape
#             ), "Input weight must be either a scalar or match the existing shape."
#             assert weight.shape[-1] == 1, "Pool dimension size must be 1!"

#         self.mt["weight"] = weight

#     def set_exchange_rate(self, *exchange_rate_matrix_rows: _Union[list, tuple]):
#         """
#         Build system exchange matrix.

#         Args:
#             *exchange_rate_matrix_rows (list or tuple): list or tuple of exchange constant.
#                 Each argument represent a row of the exchange matrix in s**-1.
#                 Each element of each argument represent a single element of the row; these can
#                 be either scalar or array-like objects of shape (n_atoms,)

#         """
#         # check that every row has enough exchange rates for each pool
#         npools = 1
#         if self.bm:
#             npools += self.bm["T1"].shape[-1]
#         if self.mt:
#             npools += self.mt["T1"].shape[-1]

#         # count rows
#         assert (
#             len(exchange_rate_matrix_rows) == npools
#         ), "Error! Incorrect number of exchange constant"
#         for row in exchange_rate_matrix_rows:
#             row = _np.asarray(row).T
#             assert (
#                 row.shape[0] == npools
#             ), "Error! Incorrect number of exchange constant per row"
#             for el in row:
#                 if _np.isscalar(el):
#                     el *= _np.ones(self.n_atoms, dtype=_np.float32)
#                 else:
#                     assert _np.array_equal(el.shape, self.shape), (
#                         "Input exchange constant must be either a scalar or match the"
#                         " existing shape."
#                     )
#             # stack element in row
#             row = _np.stack(row, axis=-1)

#         # stack row
#         self.exchange_rate = _np.stack(exchange_rate_matrix_rows, axis=-1)

#         # check it is symmetric
#         assert _np.allclose(
#             self.exchange_rate, self.exchange_rate.swapaxes(-1, -2)
#         ), "Error! Non-directional exchange matrix must be symmetric."

#     def build(self):
#         """
#         Return structures for MR simulation.
#         """
#         # check that exchange matrix is big enough
#         npools = 1
#         if self.bm:
#             npools += self.bm["T1"].shape[-1]
#         if self.mt:
#             npools += self.mt["T1"].shape[-1]

#         # actual check
#         assert (
#             self.exchange_rate.shape[-1] == npools
#         ), "Error! Incorrect exchange matrix size."
#         if npools > 1:
#             assert (
#                 self.exchange_rate.shape[-2] == npools
#             ), "Error! Incorrect exchange matrix size."

#         # prepare output
#         mrtp = _asdict(self)

#         # erase unused stuff
#         mrtp.pop("n_atoms")
#         mrtp.pop("shape")

#         # get segmentation
#         seg = mrtp.pop("segmentation")

#         # electromagnetic tissue properties
#         emtp = {}
#         emtp["chi"] = mrtp.pop("chi")
#         emtp["sigma"] = mrtp.pop("sigma")
#         emtp["epsilon"] = mrtp.pop("epsilon")

#         return seg, mrtp, emtp
