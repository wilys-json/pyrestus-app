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

import os
import pandas as pd
import numpy as np
import glob
import cv2
from tqdm import tqdm
from copy import deepcopy
from pathlib import Path
from typing import Union, List
import sys
# sys.path.insert(0, '../..')
# from ..usv.utils.misc import read_DICOM_dir

np.random.seed(1337)

IMAGE_FORMATS = {'png', 'jpg', 'jpeg', 'bmp'}
VIDEO_FORMATS = {'mp4', 'mov', 'avi'}
HIDDEN_DATA = '.randomized'
OUTPUT_DIR = 'outputs'


# Copy and paste from USV module
# TO-DO: resolve package import issues
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


def listdir(path:str, recursive:bool=False)->list:
   """
   List files in a directory.
   """
   if recursive:
       return read_DICOM_dir(path)

   if os.path.exists(path):
       return glob.glob(os.path.join(path, "*"))


def duplicate(file_list:list, split_factor:float=0.3)->list:
   """
   Shuffle the input list and repeat `split_factor` percentage of list.
   """
   assert (0 < split_factor <= 1), \
    "Splitting Factor (f) can only be 0 < f <= 1."
   list1 = deepcopy(file_list)
   list2 = deepcopy(file_list)
   np.random.shuffle(list1)
   np.random.shuffle(list2)
   split = int(len(list2) * split_factor * -1)
   if split == 0: return list1
   return list1 + list2[split:]


def shuffle(file_list:list, selection_factor:float=0.3)->list:
   """
   Shuffle the input list and select the `selection_factor` portion.
   """
   assert (0 < selection_factor <= 1), \
    "Splitting Factor (f) can only be 0 < f <= 1."
   new_list = deepcopy(file_list)
   np.random.shuffle(new_list)
   selection = int(len(new_list) * selection_factor * -1)
   return new_list[selection:]

def generate_video(video_file:str , idx:int, folder:str='output'):
   """
   Generate a video from `video_file` with `idx`
   in the lower left corner in `folder`.
   """
   cap = cv2.VideoCapture(video_file)
   frame_width = int(cap.get(3))
   frame_height = int(cap.get(4))
   padding = 50
   org = (padding, frame_height - padding)
   font = cv2.FONT_HERSHEY_SIMPLEX
   fontScale = 1
   color = (255, 255, 255)
   thickness = 2


   out = cv2.VideoWriter('{}/{}.avi'.format(folder,
        str(idx)), cv2.VideoWriter_fourcc('M','J','P','G'),
        cap.get(cv2.CAP_PROP_FPS), (frame_width,frame_height))
   while cap.isOpened():
       ret, frame = cap.read()
       if ret:
           cv2.putText(frame, str(idx), org, font,
                      fontScale, color, thickness, cv2.LINE_AA)
           out.write(frame)
       else:
           break

   out.release()
   cap.release()


def generate_image(image_file:str , idx:int, padding:int=50, folder:str='output'):
    """
    Generate an image from `image_file` with `idx`
    in the lower left corner to `folder`.
    """
    img = cv2.imread(image_file)
    h, w, c = img.shape
    org = (padding, h - padding)
    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 1
    color = (255, 255, 255)
    thickness = 2

    cv2.putText(img, str(idx), org, font,
                fontScale, color, thickness, cv2.LINE_AA)
    cv2.imwrite('{}/{}.png'.format(folder, str(idx)), img)


def generate_files(timestamp, shuffled_list, extension, folder='output'):
   if not os.path.exists(folder):
       os.mkdir(folder)
   file_df = pd.DataFrame(shuffled_list)
   file_df = file_df.reset_index()

   file_df.to_csv(os.path.join(folder,
                              '{}_{}.csv'.format(HIDDEN_DATA, timestamp)),
                 index=False, header=False)

   tqdm.pandas()

   """
   # DEPRECATED: enumerating the rows.

   for i, (index, file) in enumerate(file_df.values):
       if extension.intersection(VIDEO_FORMATS):
           generate_video(file, index, folder)
       else:
           generate_image(file, index, folder)
       print("generating {} / {} files...".format(i+1, len(file_df)))
   """
   if extension.intersection(VIDEO_FORMATS):
       (file_df.reset_index()
               .progress_apply(lambda row: generate_video(row[0],
                                           row['index'],
                                           folder=folder), axis=1))
   else:
      (file_df.reset_index()
              .progress_apply(lambda row: generate_image(row[0],
                                          row['index'],
                                          folder=folder), axis=1))


def randomize(timestamp, files_path, selection_factor=0.2,
             duplicate_factor=0.3, output_folder='output',
             recursive=False):

   assert os.path.exists(files_path), "File path not found."

   file_list = listdir(files_path, recursive)
   file_list = [str(f) for f in file_list if not str(f.stem).startswith('.')]
   extensions = set([(file.split('.')[-1]).lower() for file in file_list])
   invalid_formats = list(
                    extensions.difference(VIDEO_FORMATS.union(IMAGE_FORMATS))
                    )

   if invalid_formats:
       raise ValueError('Invalid file formats: {}'.format(invalid_formats))
   if len(extensions.intersection(VIDEO_FORMATS)) > 1:
       raise ValueError('Multiple file type found. Please unify file formats.')

   print("Randomizing {} files".format(len(file_list)))
   file_list = shuffle(file_list, selection_factor)
   file_list = duplicate(file_list, duplicate_factor)

   print("Randomization done.\n {} files will be generated: ".format(len(file_list)))
   generate_files(timestamp, file_list, extensions, folder=output_folder)

   print("Randomized files generated. Please checkout files in {} .".format(output_folder))
