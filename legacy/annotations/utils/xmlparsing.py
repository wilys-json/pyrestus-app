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

from pathlib import Path
import xml.etree.ElementTree as ET
from typing import List, Union


__all__ = [
    'get_tag',
    'get_frame_size',
]

def get_tag(xml_file: Path, tag: str, how: str = 'all'):
    """
    Parse XML tags.
    """
    assert how in ['once', 'all'], \
        f"Tag Extraction can only be `once` or `all`. Got {how}."

    tree = ET.parse(xml_file)
    root = tree.getroot()

    if how == 'once':
        return root.find(tag)

    return root.findall(tag)


def get_frame_size(xml_file: List[Path],
                   image_tag: str = './image',
                   width_tag: str = 'width',
                   height_tag: str = 'height',
                   overlay: bool = True):
    """
    Helper function to get frame size.
    """

    frame_size = []

    for file in xml_file:
        img_tag = get_tag(file, image_tag, how='once')
        frame_size += [(tuple(map(int, (img_tag.attrib[width_tag],
                                        img_tag.attrib[height_tag]))))]

    if overlay:
        assert len(set(frame_size)) == 1,\
            "Frame Size for all image must be the same for overlaying."
        return frame_size[0]

    return frame_size
