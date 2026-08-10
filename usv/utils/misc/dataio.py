import cv2
import math
from itertools import chain
from joblib import cpu_count
from pathlib import Path
from datetime import datetime
from typing import Tuple, Union, List
from .formatting import format_filename

__all__ = ['create_video_writer', 'read_DICOM_dir']

def create_video_writer(format:str,
                         frame_size:Tuple[int],
                         fps:float,
                         codec:str='MJPG',
                         output_dir:str='',
                         **kwargs)->cv2.VideoWriter:

    filename = format_filename(**kwargs)

    if not filename : return None

    if output_dir:
        Path(str(output_dir)).mkdir(parents=True, exist_ok=True)
        filename = output_dir / f'{filename}.{format}'
        if kwargs.get('exist_ok', True) is False:
            if filename.exists():
                return None

    fourcc = cv2.VideoWriter_fourcc(*codec)

    return cv2.VideoWriter(str(filename), fourcc, fps, frame_size)

# def _is_dir(path:Union[Path, str])->bool:
#
#     try:
#         file = open(Path(str(path)), 'r')
#         return False
#     except IsADirectoryError:
#         return True

def _read_DICOM_dir(dicom_dir:Union[Path, str], l:list, sorted=False)->List[Path]:

    if not Path(str(dicom_dir)).is_dir():
        return l

    for item in Path(str(dicom_dir)).iterdir():

        l += (_read_DICOM_dir(item, l, sorted) if item.is_dir() else
            [Path(str(item))])

    if sorted:
        l.sort()

    return list(set(l))

def read_DICOM_dir(dicom_dir:Union[Path, str], sorted=False)->List[Path]:

    return _read_DICOM_dir(dicom_dir, [], sorted)


def create_file_batch(dicom_dir:Union[Path, str], **kwargs):

    dicoms = _read_DICOM_dir(dicom_dir, **kwargs)
    batch_size = math.ceil(len(dicoms) / cpu_count())

    return [dicoms[i:i+batch_size] for i in range(0, len(dicoms), batch_size)]
