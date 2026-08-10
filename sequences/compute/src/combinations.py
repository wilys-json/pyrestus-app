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

import pandas as pd
import numpy as np
from itertools import permutations

def find_cluster_indices(sequence):
    """
    Find the K+1 indices of duplicated numerical values (k-th elements).

    Arg:
        sequence: Sorted 1D array or list of numerical values, e.g. timestamps
    Return:
        indices : A list of slicing indices that cluster identifical values into nested list.

    Time Complexity: O(N)
    """
    indices = []
    pivot_val = sequence[0]
    for i, val in enumerate(sequence):
        if val != pivot_val:
            indices += [i]
            pivot_val = val
    indices += [len(sequence)]
    return indices


def cluster(sequence):
    """
    Return a nested list of spatial or temporal point with the same value
    Arg:
        sequence : 2D array or list of tuples - event name in 1st col, timestamp in 2nd col
    Return:
        seq_group : a nested list with clustered points

    Time Complexity: O(N)
    """
    events, timestamp = pd.DataFrame(sequence).T.values
    indices = find_cluster_indices(timestamp)

    seq_group = []
    p = 0
    for i in indices:
        seq_group += [events.tolist()[p:i]]
        p = i

    return seq_group


def group_permute(sequence_groups):
    """
    Return a nested list of permuted list of event/feature.
    Arg:
        sequence_groups : a nested list of clustered feature of the same value
    Return:
        seq_list: a nested of permuted and clustered event/features

    Time Complexity: O(N!)
    """
    seq_list = []
    for group in sequence_groups:
        temp = []
        for perm in permutations(group):
            temp += [perm]
        seq_list += [temp]
    return seq_list


def list_possible_combinations(sequence, sep='-'):
    """
    List all possible combinations of event sequences given identical (concurrent) timestamps.
    Arg:
        sequence : a list of tuples of (label, timestamp)
    Return:
        out : a dictionary with index (key) and possible sequence (value)
        k : number of possible combinations
    """
    permuted_clustered = group_permute(cluster(sequence))
    l = [len(group) for group in permuted_clustered]
    k = np.prod(l)  # number of possible combinations
    out = (pd.concat([pd.DataFrame(group * (k // len(group)))
                    for group in permuted_clustered], axis=1)
           .apply(lambda x : sep.join(x), axis=1)
           .to_dict())
    return out, k
