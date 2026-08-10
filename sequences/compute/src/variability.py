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


from typing import List
from itertools import product
from scipy.stats import entropy
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, '..')
from .mlcs import longest_common_subsequence, mlcs_leveled_DAG

__all__ = [
    "extract_variability"
]


FUNCTIONS = [
    "sequence_diversity",
    "sequence_adhesiveness",
    "execution_variability",
    "execution_entropy",
]


def sequence_diversity(sequences: pd.Series, *args, **kwargs) -> float:
    """
    Return an index of 0 to 1, indicating how diverse the seuqnces are.
    """
    size = sequences.values.size
    if size == 1:
        return 0.0
    return np.unique(sequences.values).size / size


def sequence_adhesiveness(sequences: pd.Series, characters: list,
                      *args, **kwargs) -> float:
    """
    Return an index of 0 to 1, indicating how similar / coheisve
    the sequences are.
    """

    if sequences.values.size == 1:
        return 1.0
    max_mlcs = max([len(s) for s in mlcs_leveled_DAG(
        np.unique(sequences.values), characters)])
    return max_mlcs / len(characters)


def execution_variability(sequences: pd.Series, *args, **kwargs) -> float:
    """
    Return an index of 0 to 1, indicating how the sequences vary across
    different trials.
    """

    size = sequences.values.size

    if size == 1:
        return 0.0

    var_matrix = np.zeros((size, size))

    # Pairwise comparison
    for i, seq1 in enumerate(sequences.values):
        for j, seq2 in enumerate(sequences.values):
            var_matrix[i, j] = longest_common_subsequence(
                seq1[0], seq2[0], normalized=True)[-1]

    triu_idx = np.triu_indices(size, 1)  # the upper triangle of the matrix
    exec_sim = var_matrix[triu_idx].sum() / triu_idx[0].size  # Similarity

    return 1 - exec_sim


def execution_entropy(sequences: pd.Series, base=2, *args, **kwargs) -> float:
    """
    Shannon's entropy. Default base 2.
    """
    return entropy(sequences.value_counts(), base=base)


def extract_variability(df: pd.DataFrame, chars: List[str], levels: List[str],
                        functions: List[str] = FUNCTIONS) -> pd.DataFrame:
    """
    Calculate designated variability measures of the input `df`.
    @parmas
    df : input pd.DataFrame containing sequences represented as strings.
    chars : the characters to represent
    levels : the group labels
    functions : variability functions to compute
    """

    vars_dict = vars()
    funcs = {func: vars_dict[func] for func in functions}

    # Find indices of input levels
    levels = sorted(np.argwhere(
        np.array([(idx in levels) * 1 for idx in df.index.names]) == 1).ravel())

    # Return `None` if the input level labels
    if len(levels) == 0:
        return

    indices = product(
        *[list(np.unique(df.index.get_level_values(n))) for n in levels])
    variability = dict()
    for index in indices:

        try:

            if levels[0] != 0:
                try:
                    first_idx, sub_idx = index
                    sequences = df.xs(
                        first_idx, level=df.index.names[first_idx]).loc[sub_idx]
                except ValueError:
                    first_idx = index[0]
                    sequences = df.xs(
                        first_idx, level=df.index.names[first_idx])

            else:
                sequences = df.loc[index]

        except KeyError:
            continue

        variability[index] = dict()

        for function in functions:
            variability[index][function] = funcs[function](
                sequences, characters=chars)

        variability[index]['n'] = len(sequences)

    return pd.DataFrame(variability).T
