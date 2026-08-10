import numpy as np
import cv2
from typing import Tuple, Union, List
from math import log


np.random.seed(0)

__all__ = [
    'detect_lines',
    'find_Xbounds',
    'clahe'
]

THETA = {
    'convex' : 60,
    'linear' : 180,
}

LINES_FILTER = {
    'linear' : lambda x : x[np.any(x==0, axis=1)],
    'convex' : lambda x : x[np.any(x!=0, axis=1)]
}

def clahe(img, clipLimit=2, tileGridSize=(7,7)):
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=clipLimit, tileGridSize=tileGridSize)
    img = clahe.apply(img)
    return img

def detect_lines(image:np.ndarray,
                 kernel:Tuple[int],
                 theta:int)->np.ndarray:
        """
        Detect lines using:
        (1) Gaussian Blurring,
        (2) Canny Edge Detection,
        (3) Hough Line Transform.
        """
        # Canny edge detection
        cimg = cv2.Canny(cv2.GaussianBlur(image,
                                          kernel,
                                          0), 0, 255)

        # Hough line detection
        return cv2.HoughLines(cimg, 1,
                               np.pi / 180,
                               theta, None, 0, 0)


def _find_Xbounds(image:np.ndarray,
                  kernel:Tuple[int],
                  transducer:str)->List[Union[None, int]]:

    """
    Helper function to identify left & right most point of lines detected.
    """

    lines = detect_lines(image, kernel, THETA[transducer])

    # Identify left & right most lines
    if lines is not None:
        lines = lines.ravel().reshape(-1,2)
        cut_off_points = LINES_FILTER[transducer](lines)

        # find left and right-most point (min & max on X-axis)
        if cut_off_points.shape[0] != 0:
            cut_off_points = cut_off_points.ravel().reshape(-1,2)
            right = abs(int(cut_off_points.max(axis=0)[0]))
            left = abs(int(cut_off_points.min(axis=0)[0]))
            return [left, right]

    # None if no lines detected
    return [None]


def find_Xbounds(video,
                kernel:Tuple[int],
                transducer:str,
                padding:int=5)->Tuple[Union[None, int]]:

    assert len(video[0].shape) in [2, 3], \
        "find_Xbound only accepts array of shapes 2 or 3."

    # Set limits
    Xmin, Xmax = 0, video[0].shape[1]

    # Random sampling log(N) number of frames
    length = len(video)
    samples = int(log(length))
    idx = np.random.randint([length] * samples)

    # Find min & max limits with padding
    edges = [_find_Xbounds(video[i], kernel, transducer) for i in idx]
    edges = np.unique(np.array(edges).ravel())
    left = np.clip(edges.min() - padding, Xmin, Xmax)
    right = np.clip(edges.max() + padding, Xmin, Xmax)

    return (left, right)
