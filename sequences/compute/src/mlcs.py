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

"""
Implementation of Graph Model for MLCS
source: Peng, Z., & Wang, Y. (2017).
A Novel Efficient Graph Model for the Multiple Longest Common Subsequences
(MLCS) Problem. Frontiers in genetics, 8, 104.
"""
import numpy as np
from typing import List
from dataclasses import dataclass, field
from typing import Set, Tuple
from math import inf


__all__ = [
    'longest_common_subsequence',
    'mlcs_leveled_DAG'
]


"""
Local Data Structure
"""
# Imeplementation of Node of Level-DAG

@dataclass
class Node:
    symbol: str
    match_point: Tuple[int]
    successors: set = field(default_factory=set)
    partial_lcs: Set[str] = field(default_factory=set)

    def __hash__(self):
        return hash(self.match_point) + hash(self.symbol)

    def __eq__(self, other):
        return (self.match_point == other.match_point and
                self.symbol == other.symbol and
                self.partial_lcs == other.partial_lcs)

    def __repr__(self):
        return f'{(self.symbol, self.match_point)}'

    def inherit_lcs(self, previous_lcs):
        if not previous_lcs:
            self.partial_lcs.add(self.symbol)
        else:
            for lcs in previous_lcs:
                self.partial_lcs.add(lcs + self.symbol)

    def add_successor(self, successor):
        self.successors.add(successor)

    def has_no_successors(self):
        return len(self.successors) == 0


"""
Helper Data Structure
"""

# Helper functions


def make_successor_list(input_string: str, check: str) -> np.ndarray:
    """
    Return the successor list of `input_string`.
    """
    assert len(check) == 1
    successor_list = []
    pivot = 0
    end = len(input_string)

    for i, character in enumerate(input_string):
        if character == check:
            successor_list[pivot:i] = [i + 1] * (i - pivot + 1)
            pivot = i + 1

    if pivot < end + 1:
        successor_list[pivot:end] = [-1] * (end - pivot + 1)

    return np.array(successor_list)


def make_successor_tables(sequences: List[str], characters: List[str]) -> np.ndarray:
    """
    Implementation of Successor Tables as np.ndarray.
    Return Successor Tables (ST).
    Preprocessing Step 0 in Peng & Wang (2017)'s algorithm.
    """
    col = np.array([len(s) for s in sequences]).max() + 1
    row = len(characters)
    successor_tables = np.zeros((len(sequences), row, col), dtype=np.int32)

    for i, c in enumerate(characters):
        for j, s in enumerate(sequences):
            successor_tables[j, i] = make_successor_list(s, c)

    return successor_tables


"""
The Leveled-DAG Algorithm.
"""

# Helper functions


def find_outdated_nodes(ldag):
    with_incoming_edges = set()
    for node in ldag:
        with_incoming_edges.update(node.successors)
    return ldag - with_incoming_edges


def remove_outdated(leveled_DAG: Set[Node], findall=False) -> Set[Node]:

    outdated_nodes = find_outdated_nodes(leveled_DAG)

    for node in outdated_nodes:
        for successor in node.successors:
            append_lcs = set()
            outdated_plcs_length = max([len(lcs) for lcs in node.partial_lcs]) if len(
                node.partial_lcs) > 0 else 0
            successor_plcs_length = max([len(lcs) for lcs in successor.partial_lcs]) if len(
                successor.partial_lcs) > 0 else 0
            symbol = successor.symbol

            if outdated_plcs_length == 0:
                append_lcs.add(symbol)
            else:
                for lcs in node.partial_lcs:
                    append_lcs.add(lcs + symbol)

            if findall:  # common sequences
                successor.partial_lcs.update(append_lcs)

            else:
                if outdated_plcs_length >= successor_plcs_length:
                    successor.partial_lcs = append_lcs

                if outdated_plcs_length == (successor_plcs_length - 1):
                    successor.partial_lcs.update(append_lcs)

    return leveled_DAG - outdated_nodes


def mlcs_leveled_DAG(sequence, characters, findall=False) -> Set[str]:
    """
    Implementation of Leveled-DAG algorithm in Weng & Pang (2017).
    """

    successor_table = make_successor_tables(sequence, characters)

    current_level = []
    next_level = []
    source = Node('', (0,) * len(sequence))
    end = Node('', (inf,) * len(characters))

    current_level += [source]
    leveled_DAG = {source}

    while current_level:
        next_level = []
        for node in current_level:
            for i, mp in enumerate(np.array([successor_table[k, :, p]
                                             for k, p in enumerate(node.match_point)]).T):
                if -1 not in mp:
                    new_node = Node(characters[i], tuple(mp))
                    if new_node not in leveled_DAG:
                        node.add_successor(new_node)
                    else:
                        for existing_node in leveled_DAG:
                            if existing_node == new_node:
                                node.add_successor(existing_node)
                    next_level.append(new_node)
                    leveled_DAG.add(new_node)

            if node.has_no_successors():
                leveled_DAG.add(end)
                node.add_successor(end)
        leveled_DAG = remove_outdated(leveled_DAG, findall)
        current_level = next_level

    while {end}.difference(leveled_DAG):
        leveled_DAG = remove_outdated(leveled_DAG, findall)

    output = list(leveled_DAG)[0].partial_lcs
    max_len = max([len(s) for s in output])
    return [s for s in output if len(s) == max_len]


# DP implementation of LCS

def longest_common_subsequence(s1: str, s2: str,
                               normalized=False) -> Tuple[str, int]:

    paths = [(-1, 0), (0, -1), (-1, -1)]

    # Pad the strings
    s1 = chr(99999) + s1
    s2 = chr(99998) + s2

    # Initialize table
    lcs_table = np.zeros((len(s1), len(s2)), dtype=np.uint32)
    ref_table = np.zeros((len(s1), len(s2)), dtype=np.uint32)

    # Enumerate through the characters
    for i, c1 in enumerate(s1):
        for j, c2 in enumerate(s2):

            if i * j == 0:
                continue  # Set padding column and row to 0

            if c1 == c2:
                lcs_table[i, j] = lcs_table[i - 1, j - 1] + 1  # Match strings
                ref_table[i, j] = 2
            else:
                lcs_table[i, j] = max(
                    lcs_table[i - 1][j],  lcs_table[i][j - 1])
                ref_table[i, j] = 0 if lcs_table[i -
                                                 1][j] > lcs_table[i][j - 1] else 1

    common_subsequence = []

    idx1, idx2 = len(s1) - 1, len(s2) - 1
    while idx1 * idx2 != 0:

        if ref_table[idx1, idx2] == 2:
            assert s1[idx1] == s2[idx2], "Unexpected Error"
            common_subsequence += [s1[idx1]]

        [idx1, idx2] = np.array([idx1, idx2]) + paths[ref_table[idx1, idx2]]

    lcs = lcs_table.max()

    assert len(common_subsequence) == lcs

    if normalized:
        return ''.join(common_subsequence[::-1]), lcs / (max(len(s1) - 1, len(s2) - 1))

    return ''.join(common_subsequence[::-1]), lcs


def is_lcs(main_string, substring):
    return substring in longest_common_subsequence(main_string, substring)[0] 
