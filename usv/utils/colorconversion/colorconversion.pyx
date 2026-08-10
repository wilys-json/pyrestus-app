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
import cv2
from numpy import float32
from numpy cimport float32_t
from numpy import uint8
from numpy cimport uint8_t
from numpy cimport ndarray
cimport numpy as np
cimport cython

ctypedef float32_t FLOAT
ctypedef uint8_t INT

__all__ = ['convert_color']

cdef np.ndarray[INT, ndim=3] yuv2rgb(np.ndarray[INT, ndim=3] img):
  return cv2.cvtColor(img, cv2.COLOR_YUV2RGB)


COLOR_CONVERSION = {
    'RGB' : (lambda x : x),
    'YBR_FULL_422' : yuv2rgb,
}

@cython.boundscheck(False)
def convert_color(ndarray[INT, ndim=4] img,
                  tuple coordinates,
                  str mode):

  cdef int frame = img.shape[0]
  cdef int channels = img.shape[3]
  cdef int X0 = coordinates[0]
  cdef int Y0 = coordinates[1]
  cdef int X1 = coordinates[2]
  cdef int Y1 = coordinates[3]
  cdef int h = Y1-Y0
  cdef int w = X1-X0

  img = img[:, Y0:Y1, X0:X1, :]
  func = COLOR_CONVERSION[mode]

  for i in range(frame):
    img[i] = func(img[i])


  return img
