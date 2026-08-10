"""
source: Peng, Z., & Wang, Y. (2017).
A Novel Efficient Graph Model for the Multiple Longest Common Subsequences
(MLCS) Problem. Frontiers in genetics, 8, 104.
"""
import numpy as np
import sys
sys.path.insert(0, '..')
from src.mlcs import make_successor_tables, mlcs_leveled_DAG

# Unit tests

def test_make_successor_tables()->None:

    """
    Test case extracted from Peng and Wang (2017).
    """

    seqs = [
        'ACTAGCTA',
        'TCAGGTAT'
    ]
    chars = ['A', 'C', 'G', 'T']

    expected = np.array([
        [
            [1,4,4,4,8,8,8,8,-1],
            [2,2,6,6,6,6,-1,-1,-1],
            [5,5,5,5,5,-1,-1,-1,-1],
            [3,3,3,7,7,7,7,-1,-1]

        ],
        [
            [3,3,3,7,7,7,7,-1,-1],
            [2,2,-1,-1,-1,-1,-1,-1,-1],
            [4,4,4,4,5,-1,-1,-1,-1],
            [1,6,6,6,6,6,8,8,-1]
        ]
    ])

    assert np.array_equal(make_successor_tables(seqs,chars), expected)


def test_mlcs_leveled_DAG():
    """
    Test case extracted from Peng & Wang (2017).
    """
    seqs = [
        'ACTAGCTA',
        'TCAGGTAT'
    ]
    chars = ['A', 'C', 'G', 'T']

    expected = {
        'TAGTA',
        'CAGTA'
    }

    output = mlcs_leveled_DAG(seqs, chars)

    assert not expected.symmetric_difference(output), \
        f"""`mlcs_leveled_DAG` output : {output}
                 expect: {expected}"""


def main():
    test_make_successor_tables()
    test_mlcs_leveled_DAG()


if __name__ == '__main__':
    main()
