#################################################################################
# MIT License                                                                   #
#                                                                               #
# Copyright (c) 2021 Wilson Lam                                                 #
#                                                                               #
# Permission is hereby granted, free of charge, to any person obtaining a copy  #
# of this software and associated documentation files (the "Software"), to deal`#
# in the Software without restriction, including without limitation the rights  #
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell     #
# copies of the Software, and to permit persons to whom the Software is         #
# furnished to do so, subject to the following conditions:                      #
#                                                                               #
# The above copyright notice and this permission notice shall be included in all#
# copies or substantial portions of the Software.                               #
#                                                                               #
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR    #
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,      #
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE   #
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER        #
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, #
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE #
# SOFTWARE.                                                                     #
#################################################################################

import numpy as np
from numpy import float64
from numpy cimport float64_t
cimport numpy as np
cimport cython

__all__ = ['get_distance_matrix']

@cython.boundscheck(False)
def get_distance_matrix(int[:,::1] arr1, int[:,::1] arr2):

  cdef double d = 0;
  cdef int N1 = arr1.shape[0]
  cdef int N2 = arr2.shape[0]
  cdef int data_dims = arr1.shape[1]
  cdef int i, j, k

  empty_array = np.empty(shape=(N1, N2), dtype=float64)
  cdef double[:, :] distance_matrix = empty_array


  for i in range(N1):
    for j in range(N2):
      d = 0
      for k in range(data_dims):
        d += (arr1[i,k] - arr2[j,k]) ** 2
      distance_matrix[i,j] = d

  return np.sqrt(np.asarray(distance_matrix, dtype=float64))
