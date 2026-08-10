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

from tqdm_batch import batch_process
from joblib import cpu_count
from .utils import (format_filename, create_video_writer,
                    read_DICOM_dir, format_sequence_info,
                    clahe)
import pydicom
import numpy as np
import pandas as pd
import time
import datetime
import math
import cv2
import warnings
import yaml
from PIL import Image
from pathlib import Path
from datetime import datetime
from dateutil import parser
from pathlib import Path
from pydicom import FileDataset
from dataclasses import dataclass
from typing import Tuple, Union, List, Callable
from warnings import warn
from pydicom.errors import InvalidDicomError
from operator import itemgetter
import pyximport
pyximport.install()

__all__ = ['UltrasoundVideo', 'USVBatchConverter']

np.random.seed(0)
warnings.formatwarning = (lambda message, category,
                          filename, lineno, line:
                          f'{category.__name__}: {message}')

"""
Global Variables & Lambda helper functions
"""

def DEFAULT_FUNCTION(x): return x


VIDEO_FORMATS = {'avi', 'mp4'}

IMAGE_FORMATS = {'png', 'jpg'}

US_COLOR_VIDEO_DIM = 4

US_PROCESSING = ['cvtColor', 'trim']


def US_SEQUENCE(x): return getattr(x, 'SequenceOfUltrasoundRegions')

"""
Lambda functions to set attributes to `UltrasoundVideo` object
"""

US_ATTRIBUTES = (
    lambda x: (
        setattr(x, 'fps',
                1000 / float(getattr(x, 'FrameTime')))
    ),
    lambda x: (
        setattr(x, 'frame_delay',
                float(getattr(x, 'FrameTime')))
    ),
    lambda x: (
        setattr(x, 'dob', parser.parse('19000101'))
        if not getattr(x, 'PatientBirthDate')
        else setattr(x, 'dob',
                     parser.parse(getattr(x, 'PatientBirthDate')))
    ),
    lambda x: (
        setattr(x, 'pid',
                getattr(x, 'PatientID'))
    ),
    lambda x: (
        setattr(x, 'name',
                getattr(x, 'PatientName'))
    ),
    lambda x: (
        setattr(x, 'procedure',
                getattr(x, 'PerformedProcedureStepDescription'))
    ),
    lambda x: (
        setattr(x, 'start_time',
                parser.parse(getattr(x, 'ContentDate')
                             + getattr(x, 'ContentTime')))
    ),
    lambda x: (
        setattr(x, '_source_color_space',
                getattr(x, 'PhotometricInterpretation'))
    ),
    lambda x: (
        setattr(x, 'delta_x',
                getattr(US_SEQUENCE(x)[0], 'PhysicalDeltaX'))
    ),
    lambda x: (
        setattr(x, 'delta_y',
                getattr(US_SEQUENCE(x)[0], 'PhysicalDeltaY'))
    ),
    lambda x: (
        setattr(x, 'unit_x',
                getattr(US_SEQUENCE(x)[0], 'PhysicalUnitsXDirection'))
    ),
    lambda x: (
        setattr(x, 'unit_y',
                getattr(US_SEQUENCE(x)[0], 'PhysicalUnitsYDirection'))
    ),
    lambda x: (
        setattr(x, '_roi_coordinates',
                (
                    getattr(US_SEQUENCE(x)[0], 'RegionLocationMinX0'),
                    getattr(US_SEQUENCE(x)[0], 'RegionLocationMinY0'),
                    getattr(US_SEQUENCE(x)[0], 'RegionLocationMaxX1'),
                    getattr(US_SEQUENCE(x)[0], 'RegionLocationMaxY1')
                )
                )
    ),
)

US_COLOR_CONVERSION = {
    'RGB': {
        'RGB': DEFAULT_FUNCTION,
    },

    'YBR_FULL_422': {
        'RGB': (lambda x: cv2.cvtColor(x, cv2.COLOR_YUV2BGR))
    }

}


class EmptyDataWarning(Warning):
    """
    Helper class to raise warning.
    """
    pass

class MissingCacheFileError(Exception):
    """
    Helper class to raise warning.
    """
    pass

@dataclass(init=False)
class UltrasoundVideoBase(FileDataset):

    """
    Base class of `UltrasoundVideo`. Inhert from pydicom.FileDataset.
    """

    def __init__(self, file: Union[Path, str]):
        try:
            # Initialize FileDataset
            file_dataset = pydicom.dcmread(str(file))
            super().__dict__.update(file_dataset.__dict__)

        except InvalidDicomError:
            warn("no DICOM data found. Errors are expected if you attempt to operate on this object.",
                 EmptyDataWarning)
            pass

    @property
    def data(self) -> np.ndarray:
        """
        Data getter function.
        """
        if hasattr(self, 'pixel_array'):
            if len(self.pixel_array.shape) == US_COLOR_VIDEO_DIM:
                return self.pixel_array
            else:
                assert len(self.pixel_array.shape) == 3
                return np.expand_dims(self.pixel_array, axis=0)
        return np.array([], dtype=np.uint8)

    def empty(self) -> bool:
        """
        Check if data is empty.
        """
        return self.data.size == 0

    @property
    def is_video(self) -> bool:
        """
        Check if data contains video pixel array.
        """
        return len(self.pixel_array.shape) == US_COLOR_VIDEO_DIM



@dataclass
class UltrasoundVideoProcessor:

    """
    Color and dimension processor for `UltrasoundVideo`
    """

    delta_x: float = 0.0
    delta_y: float = 0.0
    transducer: str = 'linear'
    unit_x: int = 3
    unit_y: int = 3
    _codec: str = 'MJPG'
    _color_converter: Callable = None
    _smoothing_kernel: Tuple[int] = (3, 3)
    _source_color_space: str = 'RGB'
    _target_color_space: str = 'RGB'
    _use_cython: bool = False

    @property
    def source_color_space(self) -> str:
        return self._source_color_space

    @source_color_space.setter
    def source_color_space(self, color_space: str) -> None:
        self._source_color_space = color_space
        self.init_color_converter()

    @property
    def target_color_space(self) -> str:
        return self._target_color_space

    @target_color_space.setter
    def target_color_space(self, color_space: str) -> None:
        self._target_color_space = color_space
        self.init_color_converter()

    @property
    def codec(self) -> str:
        return self._codec

    @codec.setter
    def codec(self, codec: str) -> None:
        self._codec = codec

    @property
    def color_converter(self) -> Callable:
        return self._color_converter

    def init_color_converter(self) -> None:
        self._color_converter = (US_COLOR_CONVERSION[self.source_color_space]
                                                    [self.target_color_space])

    def cvtColor(self, img: np.ndarray) -> np.ndarray:
        assert len(img.shape) in [2, 3]
        if self.color_converter is None:
            self.init_color_converter()
        return self.color_converter(img)

    def trim(self, img: np.ndarray) -> np.ndarray:
        X0, Y0, X1, Y1 = self._roi_coordinates
        return img[Y0:Y1, X0:X1, :]

    def smooth(self, img: np.ndarray) -> np.ndarray:
        return cv2.GaussianBlur(img, self._smoothing_kernel, 0)

    # TODO: Imeplement Reverse Scan Conversion (RSC)
    def reverse_scan_conversion(self): pass

    def process(self, img: np.ndarray,
                processing: List[Callable] = US_PROCESSING) -> np.ndarray:
        for func in processing:
            try:
                img = getattr(self, func)(img)
            except TypeError:
                warn(f'{func} is not callable.', RuntimeWarning)
                continue
            except AttributeError:
                warn(f'{self.__class__} has no functions called `{func}`.',
                     RuntimeWarning)
                continue
        return img


@dataclass(init=False)
class UltrasoundVideoIO(UltrasoundVideoBase):

    """
    Helper class to handle Input/Ouput of UltrasoundVideo resources.
    """

    name: str = ''
    pid: str = ''
    start_time: datetime = datetime(1900, 1, 1)
    fps: float = 0.0
    # output_format = 'avi'
    _output_dir: Path = Path('output')
    _roi_coordinates: Tuple[int] = (0, 0, 0, 0)

    def __init__(self, file: Union[Path, str]):
        UltrasoundVideoBase.__init__(self, file)

    @property
    def output_dir(self) -> str:
        return self._output_dir

    @output_dir.setter
    def output_dir(self, output_dir: str) -> None:
        self._output_dir = Path(output_dir)

    @property
    def orig_size(self):
        return self.data.shape[1:3]

    @property
    def roi_size(self):
        """
        Return the size of the Region of Interest
        """
        X0, Y0, X1, Y1 = self._roi_coordinates
        return self.data[:, Y0:Y1, X0:X1, :].shape[1:3]

    def VideoWriter(self, video_format, codec='MJPG', **kwargs) -> cv2.VideoWriter:
        processing = kwargs.get('processing', US_PROCESSING)
        frame_size = [self.orig_size[::-1],
                      self.roi_size[::-1]]['trim' in processing]
        return create_video_writer(format=video_format,
                                   frame_size=frame_size,
                                   fps=self.fps,
                                   name=self.name,
                                   pid=self.pid,
                                   start_time=self.start_time,
                                   output_dir=self.output_dir,
                                   codec=kwargs.get('codec', self.codec),
                                   **kwargs)

    def ImageWriter(self, image_format: str = 'png', **kwargs) -> Callable:
        filename = format_filename(name=self.name,
                                   pid=self.pid,
                                   start_time=self.start_time,
                                   **kwargs)

        save_dir = self.output_dir / f'{filename}'
        if save_dir.exists():
            return None
        if kwargs.get('static', False) is False:
            save_dir.mkdir(parents=True)
        pad = len(str(len(self.data)))

        if kwargs.get('static'):
            return (lambda image:
                    cv2.imwrite(f'{self.output_dir}/{filename}.{image_format}', image))

        return (lambda i, image:
                cv2.imwrite(f'{save_dir}/{str(i).zfill(pad)}.{image_format}',
                            image))


@dataclass(init=False)
class UltrasoundVideo(UltrasoundVideoIO, UltrasoundVideoProcessor):

    """
    Main class for processing Ultrasound DICOM files.
    """

    dob: datetime = datetime(1900, 1, 1)
    procedure: str = ''
    _use_cython: bool = False

    def __init__(self, file: Union[str, Path], **kwargs):

        UltrasoundVideoIO.__init__(self, file)

        # Set attributes w.r.t. Metadata
        for setter in US_ATTRIBUTES:
            try:
                setter(self)
            except AttributeError:
                # warn(f"Unable to find attribute for {setter}")
                pass

        # Override metadata
        for attr, value in kwargs.items():
            setattr(self, attr, value)

    def __len__(self)->int:
        return len(self.data)

    def __iter__(self):
        if not self.empty():
            for i in range(len(self.data)):
                yield self.data[i]

    def __getitem__(self, idx):
        try:
            return super().__getitem__(idx)
        except KeyError:
            if not self.empty():
                return self.data[idx]

    def get(self, *args):
        """
        Overloading function.
        if `args` is dict.get() like, return Dataset.get(*args)
        if `args` is dictionary keys like, return Dataset.get('key_string')
        if `args` is int, return cropped Image by index.
        """
        if len(args) > 1:
            return super().get(*args)

        if not isinstance(args[0], int):
            return super().get(args[0])

        if not self.empty():
            idx = args[0]
            X0, Y0, X1, Y1 = self._roi_coordinates
            img = self.cvtColor(self.data[idx][Y0:Y1, X0:X1, :])
            return Image.fromarray(img)

    @property
    def channels(self):
        return self.data.shape[-1]

    def show(self, **kwargs):
        """
        Play Ultrasound Video.
        """
        if not self.empty():
            frame_delay = int(self.get('frame_delay', 1))
            processing = kwargs.get('processing', US_PROCESSING)
            for i, image in enumerate(self.data):
                image = self.process(image, processing)
                cv2.imshow(f'{self.name} at {self.start_time}', image)

                key = cv2.waitKey(frame_delay)

                if (i == len(self.data) - 1) or key == 27:
                    cv2.destroyAllWindows()
                    break

            cv2.waitKey(1)
            cv2.destroyAllWindows()


@dataclass
class USVBatchConverter:

    """

    Batch converter using multithreading / multiprocessing.

    Sample output -

    dicom = Path('../data/DICOM_FILES/01')  # dicom : DICOM file directory


    # Converting to avi

    converter = USVBatchConverter(backend='threading',
                              input_dir=dicom,
                              output_dir='test_output_avi',
                              output_formats=['avi'])

    %%timeit
    converter.run()  # processing: `cvtColor`, `trim`, output: `avi`
    >> 48.2 s ± 2.95 s per loop (mean ± std. dev. of 7 runs, 1 loop each)

    """

    backend: str
    input_dir: Union[Path, str]
    output_dir: Union[Path, str]
    output_formats: List[str]
    cache: Union[str, None]

    def _list_expected_outputs(self, dicoms):

        """
        Protected function - return a list of expected outputs from conversion.
        """

        output_dicoms = {dicom: UltrasoundVideo(dicom) for dicom in dicoms}
        output_filenames = dict()

        for dicom_filename, usvid in output_dicoms.items():
            if dicom_filename.name.startswith('.'): continue
            for output_format in self.output_formats:
                if output_format in VIDEO_FORMATS:
                    output_filenames.update({
                    f'{format_filename(usvid.name, usvid.pid, usvid.start_time)}.{output_format}' : str(dicom_filename)})
                else:
                    output_filenames.update({
                        format_filename(usvid.name, usvid.pid,
                        usvid.start_time) : str(dicom_filename)})
        return output_filenames


    def check_dir(self):

        """
        Returns necessary DICOM files for conversion. Skip existing files.
        """

        dicoms = read_DICOM_dir(self.input_dir)
        output_filenames = self._list_expected_outputs(dicoms)

        if self.cache:
            try:
                with open(self.cache) as file:
                    existing_files = file.read().splitlines()
            except FileNotFoundError:
                raise MissingCacheFileError("Missing cache file `dircache`, \
please use `frame_generation  -o [output_dir] -m` to generate a cach file first.")
        else:
            existing_files = set([str(file.name)
                        for file in Path(str(self.output_dir)).iterdir()])

        dicoms_to_convert = output_filenames.keys() - existing_files
        if not dicoms_to_convert: return None
        return list(itemgetter(*dicoms_to_convert)(output_filenames))



    @staticmethod
    def create_writers(io_object: UltrasoundVideoIO,
                       output_formats: List[str], **kwargs):

        """
        Prepare image / video writers for output.
        Return either or both Image or VideoWriter depending on `output_formats`.
        """

        output_writers = []
        for output_format in output_formats:
            output_writers += [io_object.VideoWriter(output_format, **kwargs)
                               if output_format in VIDEO_FORMATS else
                               io_object.ImageWriter(output_format, **kwargs)
                               if output_format in IMAGE_FORMATS else
                               DEFAULT_FUNCTION]
        return output_writers

    def convert(self, input_file: Union[Path, str],
                processing: List[str] = US_PROCESSING,
                **kwargs):

        """
        Converts `input_file` to desired `self.output_formats`.
        """
        use_clahe = kwargs.get('clahe', False)
        ultrasound_video = UltrasoundVideo(input_file,
                                           output_dir=self.output_dir,
                                           **kwargs)

        writers = USVBatchConverter.create_writers(ultrasound_video,
                                                    self.output_formats,
                                                    processing=processing,
                                                    static=(ultrasound_video.is_video == False),
                                                    **kwargs)

        if kwargs.get('roi_metadata'):
            if set(self.output_formats).intersection(IMAGE_FORMATS):
                filename = format_filename(ultrasound_video.name,
                                            ultrasound_video.pid,
                                            ultrasound_video.start_time)
                output_dir = self.output_dir / filename
                output_dir.mkdir(parents=True, exist_ok=True)
                output_pth = output_dir / 'roi_metadata.yml'
                roi_metadata = format_sequence_info(input_file)
                with open(str(output_pth), 'w') as output_file:
                    yaml.dump(roi_metadata, output_file)

        if not any(writers) :
            return
        
        for i, frame in enumerate(ultrasound_video.data):
            frame = ultrasound_video.process(frame, processing)
            if use_clahe:
                frame = clahe(frame)
            for writer in writers:
                if writer is None: continue
                try:
                    writer.write(frame)
                except AttributeError:
                    try:
                        writer(i, frame)
                    except TypeError:
                        writer(frame)
        for writer in writers:
            try:
                writer.release()
            except AttributeError:
                pass
        
        

    def batch_convert(self, batch: list, **kwargs):
        [self.convert(file, **kwargs) for file in batch]

    def run(self, **kwargs):
        dicoms = self.check_dir()  # check and skip existing files
        if not dicoms: return
        batch_process(dicoms, self.convert,
                      n_workers=cpu_count(),
                      sep_progress=True,
                      **kwargs)
