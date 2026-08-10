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
from pathlib import Path
from copy import deepcopy
from PIL import Image
from typing import List, Tuple, Union


HSV_FILTERS = {
    "b" : ((90,180,170),
              (120,255,255)),  # blue
    "g" : ((30, 0, 0),
               (80, 255, 255)),  # green
    "y" : ((22, 93, 0),
                (45, 255, 255)),  # yellow
    "r" : ((160, 85, 180),
                (180, 255, 255)), # red
    "w" : ((0, 0, 255),
                (180, 50, 255)),   # white
    "o" : ((14, 136, 116),
                (33, 255, 255))  #  orange
}

# CROPPING_RATIOS = (.256, .095, .953, .945)
CROPPING_RATIOS = (.256, .095, .953, .945)

MORPHOLOGICAL_CORRECTION = (2,2)

MORPHOLOGICAL_ITERATIONS = (1,4)

GAUSSIAN_SMOOTHING = (7,7)

BINARY_THRESHOLD = 1

OUTPUT_DIR = 'segmented'


def crop_image(img:np.ndarray,
               cropping:Tuple[float],
               keep_array=True)->Union[np.ndarray, Image.Image]:
    """
    Crop `img` w.r.t. the defined `cropping` ratio.
    """
    assert (isinstance(cropping, tuple) and
            len(cropping) == 4 and
            [type(element)
             for element in cropping] == [float] * len(cropping)), \
        "Cropping ratios must be in (float, float, float, float) format."

    img = Image.fromarray(img)
    w, h = img.size
    left_ratio, upper_ratio, right_ratio, lower_ratio = cropping
    img = img.crop((w * left_ratio, h * upper_ratio,
                    w * right_ratio, h * lower_ratio))

    if keep_array:
        return np.array(img)

    return img


def filter_image(img:np.ndarray,
                 id:str,
                 hsv_filters:List[Tuple[Tuple[float]]])->np.ndarray:
    """
    Filter specific color range from `img` w.r.t. `hsv_filters`.
    Return immediately if one of the colors identified.
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    color = np.zeros_like(img, np.uint8)
    blackimg = deepcopy(color)

    for hsv_filter in hsv_filters:
        hsv_min, hsv_max = hsv_filter
        mask = cv2.inRange(hsv, hsv_min, hsv_max)
        # imask = mask > 0
        # color[imask] = img[imask]
        color = cv2.bitwise_and(img, img, mask=mask)

    if (color == blackimg).all():
        print(f"Warning: No segmentation detected in {id}.")

    return color

def extract_segment(img:np.ndarray,
                   correction:Tuple[int]=MORPHOLOGICAL_CORRECTION,
                   iterations:int=MORPHOLOGICAL_ITERATIONS,
                   smoothing:Tuple[int]=GAUSSIAN_SMOOTHING,
                   binary_threshold:int=BINARY_THRESHOLD,
                   required_corrections:bool=True)->np.ndarray:

    """
    Extract filtered segments and convert to an binary image.
    Steps:
    (1) Morphological correction : dilation & erosion
    (2) Gaussian Blurring
    """

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    corrected = gray.copy()
    if required_corrections:
        erode_iterations, dilated_iterations = iterations
        kernel = np.ones(correction, 'uint8')
        dilated = cv2.dilate(gray, kernel, iterations=dilated_iterations)
        corrected = cv2.erode(dilated, kernel, iterations=erode_iterations)
    corrected = cv2.GaussianBlur(corrected, smoothing, 0)
    ret, thresh = cv2.threshold(corrected, binary_threshold,
                                255, cv2.THRESH_BINARY)

    return thresh


def fill_contours(img:np.ndarray)->Image.Image:

    """
    Fill shape defined by a closed contour.
    """
    contours = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = contours[0] if len(contours) == 2 else contours[1]
    result = np.zeros_like(img)
    for contour in contours:
        cv2.drawContours(result, [contour], 0, (255, 255, 255), cv2.FILLED)

    return Image.fromarray(result)



def get_segmentation_mask(img_path: Union[str, Path],
                          cropping:Tuple[float]=CROPPING_RATIOS,
                          hsv_filters:List=list(HSV_FILTERS.values()),
                          correction:Tuple[int]=MORPHOLOGICAL_CORRECTION,
                          morph_iter:int=MORPHOLOGICAL_ITERATIONS,
                          smoothing:Tuple[int]=GAUSSIAN_SMOOTHING,
                          binary_threshold:int=BINARY_THRESHOLD,
                          save:bool=True, **kwargs):


    """
    Get a segmentation mask (in binary image form) from edge-defined
    segmentation images.
    """

    show_original = kwargs.get('show_original')
    show_binary = kwargs.get('show_binary')
    lines_only = kwargs.get('lines_only')
    show_mask = kwargs.get('show_mask')
    color = kwargs.get('color')
    correction = kwargs.get('correction')

    if color:
        hsv_filters = [HSV_FILTERS[color[0].lower()]]

    img = cv2.imread(str(img_path))

    if cropping:
        img = crop_image(img=img, cropping=CROPPING_RATIOS)

    color = filter_image(img=img, id=img_path, hsv_filters=hsv_filters)
    thresh = color

    thresh = extract_segment(img=color,
                            correction=correction,
                            iterations=morph_iter,
                            smoothing=smoothing,
                            binary_threshold=binary_threshold,
                            required_corrections=correction)

    if show_original:
        Image.fromarray(img).show()

    if show_binary:
        Image.fromarray(thresh).show()

    if lines_only:
        segmented_img = Image.fromarray(thresh)
    else:
        segmented_img = fill_contours(img=thresh)

    if show_mask:
        segmented_img.show()


    if save:
        output_dir = kwargs.get('output_dir')
        timestamp = kwargs.get('timestamp')
        output_dir = ((Path(output_dir) if output_dir
                     else Path(OUTPUT_DIR)))

        output_dir = output_dir / f'{Path(img_path).parent.stem}-{timestamp}'
        output_dir.mkdir(parents=True, exist_ok=True)
        segmented_img.save(output_dir / f'{Path(img_path).stem}_segmented.png')
