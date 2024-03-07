"""I/O Routines for BART files."""

from __future__ import print_function
from __future__ import with_statement

__all__ = ["read_bart", "write_bart"]

import numpy as np
import mmap
import os


def read_bart(filename: str) -> np.ndarray:
    """
    Read file in BART format. Used for BART interoperability.

    Parameters
    ----------
    filename : str
        Path of the file on disk.

    Returns
    -------
    np.ndarray
        CFL file content.

    """
    return np.ascontiguousarray(_readcfl(filename))


def write_bart(input: np.ndarray, filename: str):
    """
    Write file in BART format. Used for BART interoperability.

    Parameters
    ----------
    input : np.ndarray
        Data to be stored on disk.
    filename : str
        Path of the file on disk.

    """
    return _writecfl(input, filename)


# %% local utils
# Copyright 2013-2015. The Regents of the University of California.
# Copyright 2021. Uecker Lab. University Center Göttingen.
# All rights reserved. Use of this source code is governed by
# a BSD-style license which can be found in the LICENSE file:
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Authors:
# 2013 Martin Uecker <uecker@eecs.berkeley.edu>
# 2015 Jonathan Tamir <jtamir@eecs.berkeley.edu>
def _readcfl(name):
    # get dims from .hdr
    with open(name + ".hdr", "rt") as h:
        h.readline()  # skip
        l = h.readline()
    dims = [int(i) for i in l.split()]

    # remove singleton dimensions from the end
    n = np.prod(dims)
    dims_prod = np.cumprod(dims)
    dims = dims[: np.searchsorted(dims_prod, n) + 1]

    # load data and reshape into dims
    with open(name + ".cfl", "rb") as d:
        a = np.fromfile(d, dtype=np.complex64, count=n)
    return a.reshape(dims, order="F")  # column-major


def _writecfl(name, array):
    with open(name + ".hdr", "wt") as h:
        h.write("# Dimensions\n")
        for i in array.shape:
            h.write("%d " % i)
        h.write("\n")

    size = np.prod(array.shape) * np.dtype(np.complex64).itemsize

    with open(name + ".cfl", "a+b") as d:
        os.ftruncate(d.fileno(), size)
        mm = mmap.mmap(d.fileno(), size, flags=mmap.MAP_SHARED, prot=mmap.PROT_WRITE)
        if array.dtype != np.complex64:
            array = array.astype(np.complex64)
        mm.write(np.ascontiguousarray(array.T))
        mm.close()
        

def _read_coo(fd, n):
    header = fd.read(4096)
    
    if len(header) != 4096:
        return -1

    pos = 0
    delta = 0

    if not npsscanf(header + pos, "Type: float\n%n", delta):
        return -1

    if delta == 0:
        return -1

    pos += delta

    dim = 0

    if not npsscanf(header + pos, "Dimensions: %d\n%n", dim, delta):
        return -1

    pos += delta

    # if n != dim:
    #     return -1

    dimensions = np.ones(n, dtype=np.long)

    for i in range(dim):
        val = 0

        if not npsscanf(header + pos, "[%*d %*d %ld %*d]\n%n", val, delta):
            return -1

        pos += delta

        if i < n:
            dimensions[i] = val
        elif val != 1:
            return -1

    return dimensions

def npsscanf(s, fmt, *args):
    try:
        result = npsscanf_dict(fmt, s)
        if result is None:
            return False
        for i, arg in enumerate(args):
            arg[0] = result[i]
        return True
    except ValueError:
        return False

def npsscanf_dict(fmt, s):
    items = fmt.split()
    result = []
    for item in items:
        if item.startswith("%"):
            conversion = item[-1]
            if conversion == "d":
                pos = s.find("%d")
                if pos == -1:
                    raise ValueError("Invalid format")
                num_chars = 0
                while pos + num_chars < len(s) and s[pos + num_chars].isdigit():
                    num_chars += 1
                result.append(int(s[pos:pos + num_chars]))
                s = s[:pos] + s[pos + num_chars:]
            elif conversion == "n":
                pos = s.find("%n")
                if pos == -1:
                    raise ValueError("Invalid format")
                result.append(pos)
                s = s[:pos] + s[pos + 2:]
            else:
                raise ValueError("Unsupported conversion")
        else:
            pos = s.find(item)
            if pos == -1:
                raise ValueError("Invalid format")
            s = s[:pos] + s[pos + len(item):]
    return result

# # Example usage:
# with open("your_file.txt", "r") as file:
#     n = 3  # Specify the desired value for n
#     dimensions = read_coo(file, n)
#     if dimensions == -1:
#         print("Error reading COO format.")
#     else:
#         print("Dimensions:", dimensions)
