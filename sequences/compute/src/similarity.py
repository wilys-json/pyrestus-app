#################################################################################
# MIT License                                                                   #
#                                                                               #
# Copyright (c) 2022 Wilson Lam                                                 #
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

# Similarity measures

def similarity(seq1, seq2, method='dice'):

    valid_methods = ['dice', 'jaccard', 'overlap_coeff']
    assert method in valid_methods, \
        f"only provide the following methods: {valid_methods}; got {method}"

    seq1 = set(seq1)
    seq2 = set(se2)

    intersection = len(seq1.intersection(seq2))
    if method =='dice':
        intersection *= 2

    denom = {
        "dice" : len(seq1) + len(seq2),
        "jaccard" : len(seq1 & seq2),
        "overlap_coeff" : min(len(seq1), len(seq2))
    }

    return intersection / denom['method']


def dsc(seq1, seq2):
    return similarity(seq1, seq2, method='dice')

def jaccard(seq1, seq2):
    return similarity(seq1,seq2, method='jaccard')

def ssc(seq1,seq2):
    return similarity(seq1,seq2, method='overlap_coeff')

