import numpy as np
from pycocotools.coco import COCO
from scipy.signal import find_peaks

# default values
DELTA = 0.14783999919891358  # mm 
TIME = 34.896713 / 1000

def annot_dict(coco_obj):
    output_dict = dict()
    anns = coco_obj.dataset['annotations']
    for ann in anns:
        output_dict[(ann['image_id'], ann['category_id'])] = ann['id']
    return output_dict

def catNameToAnns(coco_obj, catName):
    anns = []
    catId = coco_obj.getCatIds(catName)[0]
    catIndex = list(coco_obj.catToImgs.keys()).index(catId)
    imgIds = coco_obj.catToImgs[catId]
    for i in imgIds:
        try:
            anns += [coco_obj.anns[coco_obj.getAnnIds(i)[catIndex]]]
        except:
            print(f'{catName} not found in annotation.')
            continue
    return anns

def get_coords(obj, structure):
    if isinstance(obj, str):
        obj = COCO(obj)
    anns = catNameToAnns(obj, structure)
    return [{ann['image_id'] : np.reshape(ann['segmentation'], (-1,2)) } for ann in anns]

def get_bbox(obj, structure):
    if isinstance(obj, str):
        obj = COCO(obj)
    anns = catNameToAnns(obj, structure)
    return[{ann['image_id'] : ann['bbox'] for ann in anns}]

def get_bbox_coords(obj, structure):
    if isinstance(obj, str):
        obj = COCO(obj)
    anns = catNameToAnns(obj, structure)
    return[{ann['image_id'] : (np.reshape(ann['segmentation'], (-1,2)), ann['bbox'])} for ann in anns]

def get_mask(obj, structure, get_coords=False):
    if isinstance(obj, str):
        obj = COCO(obj)
    anns = catNameToAnns(obj, structure)
    if not get_coords:
        return [{ann['image_id'] : obj.annToMask(ann) for ann in anns}]
    return[{ann['image_id'] : (obj.annToMask(ann), np.reshape(ann['segmentation'], (-1,2))) for ann in anns}]

def get_anchoring_pt(array, criteria):
    assert len(criteria) == 2
    axis, thres = criteria
    assert thres in ['min', 'max']
    assert axis in ['x', 'y']
    thres_val = [0, -1][thres == 'max']
    axis_val = [0, 1][axis == 'y']
    inds = np.argsort(array, axis=0)[thres_val, axis_val]
    return array[inds]

def moving_average(x, w):
    return np.convolve(x, np.ones(w), 'valid') / w

def find_contour(binary_image, direction, trim=10):
    assert direction in ['top', 'left', 'right', 'bottom', 'all']
    if direction == 'all':
        return np.concatenate([find_contour(binary_image, 'top', trim=0), find_contour(binary_image, 'bottom', trim=0)],axis=0)
    ax = int(direction in ['left', 'right'])
    arr1 = np.where(binary_image.sum(axis=ax)>0)[0]
    arr2 = []
    extracted = binary_image[:,arr1].T if direction in ['top', 'bottom'] else binary_image[arr1, :]
    for arr in extracted:
        if len(np.argwhere(arr>0)) > 0:
            arr2 += [np.argwhere(arr>0).max() if direction in ['bottom', 'right'] else np.argwhere(arr>0).min()]
    arr2 = np.array(arr2)
    if trim == 0:
        return np.array(list(zip(arr1, arr2))) if direction in ['top', 'bottom'] else np.array(list(zip(arr2, arr1)))
    return np.array(list(zip(arr1, arr2)))[trim:-trim] if direction in ['top', 'bottom'] else np.array(list(zip(arr2, arr1)))[trim:-trim]


def dist_from_orig(input, *args, **kwargs):
    return np.linalg.norm(input[1:] - input[0], axis=1)


def _get_pts(input_cnt, *args, **kwargs):
    sorted_x = input_cnt[input_cnt[:,0].argsort()]
    post = sorted_x[-1]
    ant = sorted_x[0]
    mid = (input_cnt[input_cnt[:,1].argsort()][0] 
           if kwargs.get('use_high_point')
           else sorted_x[len(sorted_x)//2])

    return ant, mid, post

def compute_curvature(input_cnt, *args, **kwargs):
    x, y, z = _get_pts(input_cnt, *args, **kwargs)
    a = np.linalg.norm(y-x)
    b = np.linalg.norm(z-y)
    c = np.linalg.norm(z-x)
    # Calculate the area of the triangle using Heron's formula
    s = (a + b + c) / 2  # semi-perimeter
    area = np.sqrt(s * (s - a) * (s - b) * (s - c))
    
    # Calculate the Menger curvature using the formula
    menger_curvature = 4 * area / (a * b * c)
    
    return menger_curvature

def curve_diff(input, *args, **kwargs):
    return np.array([compute_curvature(cnt, *args, **kwargs) for cnt in input])

def compute_approx(input, *args, **kwargs):
    return np.linalg.norm((input[1] - input[0]))

def compute_kineseq(input, disp_func, criteria='max', start=0, ma_window=3, interval=TIME, spatial_correction=DELTA, *args, **kwargs):
    
    k_func = kwargs.get('kinematic_func')
    dfargs = kwargs.get('dfargs', dict())
    disp_func = globals()[disp_func]

    # spatial temporal analysis
    if k_func:
        pivot = kwargs.get('disp_pivot', -1)
        disp = disp_func([data[pivot] for data in input[start:]], *args, **dfargs, **kwargs) * spatial_correction
        k = k_func(input[start:], *args, **kwargs) * spatial_correction
        v = moving_average(np.gradient(k, interval), ma_window)
        a = moving_average(np.gradient(v, interval), ma_window)
    else:
        disp = disp_func(input[start:], *args, **dfargs, **kwargs) * spatial_correction
        if kwargs.get('disp_only'):
                v = disp
                a = disp
        else:
            v = moving_average(np.gradient(disp, interval), ma_window)
            a = moving_average(np.gradient(v, interval), ma_window)

    # sequencing

    max_disp = disp[start:].argmax() if criteria == 'max' else disp[start:].argmin()
    pos_peaks, _ = find_peaks(a[start:])
    neg_peaks, _ = find_peaks(-1 * a[start:])

    peaks = {
        "positive peak" : pos_peaks,
        "negative peak" : neg_peaks
    }

    landmarks = kwargs.get('landmarks')

    if landmarks:
        max_reached = peaks[landmarks['max']][peaks[landmarks['max']] <= max_disp].max()
        onset = peaks[landmarks['onset']][peaks[landmarks['onset']] < max_reached].max()
        offset = (max_reached + peaks[landmarks['offset']][peaks[landmarks['offset']] > max_reached].min()) // 2

    else:
        max_reached = neg_peaks[neg_peaks <= max_disp].max()
        onset = pos_peaks[pos_peaks < max_reached].max()
        offset = (max_reached + pos_peaks[pos_peaks > max_reached].min()) // 2

    return {
        "disp" : k if k_func else disp,
        "v" : v,
        "a" : a,
        "onset" : onset,
        "max" : max_reached,
        "offset" : offset
    }