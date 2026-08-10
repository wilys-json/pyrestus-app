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

import re
import sys
import argparse
from pathlib import Path

def _find_files(folder):
    files = []
    if all(list(map(Path.is_file, list(folder.iterdir())))):
        return list(folder.iterdir())

    for child in folder.iterdir():
        files += _find_files(child)

    return files

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=str, metavar='folder',
                        help='Folder containing files to unify.')
    parser.add_argument('-t', '--pattern', type=str, metavar='pattern',
                        nargs='+', help='Regex patterns to look for.')
    parser.add_argument('-r', '--recursive', action='store_true', default=False)
    parser.add_argument('-p', '--replace', action='store_true', default=False)

    args = parser.parse_args()

    folder = Path(args.folder)

    assert folder.is_dir(), f"Cannot find folder: {args.folder}."

    if args.recursive:
        files = _find_files(folder)
    else:
        files = folder.iterdir()

    count = 0
    for file in files:

        if not args.replace:
            assert args.pattern and (len(args.pattern) == 1)
            find = lambda x : re.findall(args.pattern[0], x)
            if file.name[0] != '.':
                found = find(str(file))
                if found:
                    file.rename(file.parent / found[0])
                    count += 1

        else:
            assert args.pattern and (len(args.pattern) % 2 == 0)
            if file.name[0] != '.':
                new_name = file.name
                for orig, target in zip(args.pattern[::2], args.pattern[1::2]):
                    new_name = new_name.replace(orig, target)
                file.rename(file.parent / new_name)
                count += 1

    print(f'Renamed {count} files.')

if __name__ == '__main__':
    main()
