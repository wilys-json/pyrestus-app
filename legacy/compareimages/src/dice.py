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
import pandas as pd
import cv2
from typing import Tuple
from tqdm import tqdm
from PIL import Image
from itertools import combinations
from .utils import (inconsistent_name, create_overlapping_images,
                    read_binary, make_hyperlink)

def dice_coefficient(img1: np.ndarray, img2: np.ndarray, **kwargs) -> float:
    """
    Naive Implementation of Dice score calculation.
    """

    ignore_error = kwargs.get('ignore_error')
    index = kwargs.get('index')
    raters = kwargs.get('raters')
    shape_only = kwargs.get('shape_only')


    if ignore_error:
        if img1.shape != img2.shape and not shape_only:
            return 0.0

    else:
        assert img1.shape == img2.shape, \
        f"""Unequal image size {'' if not index else 'at '+str(index)}:\n
        `{raters[0]
           if raters
           else 'The first '}` image has shape {img1.shape}\n
           while `{raters[1]
                   if raters
                   else 'The second '}` image has shape {img2.shape}\n"""


    if shape_only:
        img1 = _get_shape_set(img1, ignore_error)
        img2 = _get_shape_set(img2, ignore_error)


    intersection, sum_of_length = (len(img1 & img2), len(img1) + len(img2) if shape_only
                            else (((img1.ravel() == img2.ravel()) * 1).sum(),
                             (img1.size + img2.size)))

    if sum_of_length == 0:
        return 0.0

    # Dice Cofficient: 2 * (A n B) / |A| + |B|
    return (2 * intersection) / sum_of_length


# Deprecated
def _get_shape1d(img: np.ndarray) -> np.ndarray:
    """
    Return the view of a 2d shape defined in a binary image.
    """
    img_dtype = img.dtype
    img = np.argwhere(img == 255)

    return img.view([('',img_dtype)]*img.shape[1])

def _get_shape_set(img: np.ndarray, ignore_error=False) -> set:

    """
    Return a set of pixel address of a shape defined by a binary `img`.
    """
    if not ignore_error:
        assert (np.unique(img) == np.array([0, 255])).all(), \
            f"{_get_shape_set.__name__} only takes a binary image."
    img = np.argwhere(img == 255)

    return set([tuple(pixel_address) for pixel_address in img])


def dice_scores(df:pd.DataFrame, **kwargs)->Tuple[pd.DataFrame, pd.DataFrame]:

    """
    Calculate image-wise and average (inter-/intra) rater Dice scores.
    """

    assert len(df.columns) > 1, \
    "DataFrame must contain more than 1 rater."

    if kwargs.get('ignore_inconsistent_name') == False:
        assert not inconsistent_name(df), \
        "DataFrame contains inconsistent names. Please check file names again."


    dice_df = pd.DataFrame()
    hyperlink_df = None
    temp_dfs = []
    tqdm.pandas()

    if kwargs.get('repeated_image'):
        indices = df.index.values
    else:
        indices = np.vectorize(lambda x: x.name)(df[df.columns[0]].values)
    # df = df.applymap(lambda x : cv2.imread(str(x), cv2.IMREAD_GRAYSCALE))

    # if kwargs.get('shape_only'):
    #     df = df.applymap(lambda x : _get_shape1d(x))

    for comb in combinations(df.columns, 2):
        rater_a, rater_b = comb
        dice_df[f"Dice-{rater_a}-{rater_b}"] = df.progress_apply(
        lambda x : dice_coefficient(read_binary(x[rater_a]),
                                    read_binary(x[rater_b]),
                                   index=x.name,
                                   raters=(rater_a, rater_b),
                                   ignore_error=kwargs.get('ignore_error'),
                                   shape_only=kwargs.get('shape_only')),
                                   axis = 1)

        if kwargs.get('create_overlapping_image'):
            if not kwargs.get('output_dir'): continue
            paths = create_overlapping_images(df[rater_a],
                                              df[rater_b],
                                              output_dir=kwargs.get('output_dir'),
                                              indices=indices,
                                              raters=(rater_a, rater_b),
                                              scale_down=kwargs.get('scale_down'))

            temp_df = pd.DataFrame(dice_df[f"Dice-{rater_a}-{rater_b}"]
                                    .astype('string') + "#" + paths)

            temp_df = temp_df.applymap(lambda x : make_hyperlink(x))
            temp_dfs.append(temp_df)

    if kwargs.get('create_overlapping_image'):
        hyperlink_df = pd.concat(temp_dfs, axis=1)
        hyperlink_df = hyperlink_df.set_index(indices)

    return (dice_df.set_index(indices),
            pd.DataFrame(dice_df.mean(axis=0), columns=['Dice Scores']),
            hyperlink_df)
