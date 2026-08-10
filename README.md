# Pyrestus: Python Research Tools for Ultrasonography in Swallowing

This is a research tool package being developed for studying Ultrasound Imaging.



## Dependencies

1. Python 3.8 or above
2. Python libraries:

- `numpy` >= 1.12
- `pandas` >=1.3
- `opencv-python` >=4.5
- `tqdm` >= 4.0
- `Pillow` >= 8.4
- `scipy` >= 1.7
- `Cython` >= 0.29


## Installing Libraries & Dependencies

### MacOS

1. Clone this repository: `git clone https://github.com/wilys-json/pyrestus`

2. Open Terminal, navigate to the program directory

3. Type `/bin/bash setup.sh` - this will set up everything you need for this program


### Windows

1. Clone this repository: `git clone https://github.com/wilys-json/pyrestus`

2. Dowload and install [Python3](https://www.python.org/ftp/python/3.8.9/python-3.8.9-amd64.exe)

3. Open Command Prompt

4. Type `python -m pip install -r requirements-core.txt`

#### Legacy modules:

- [Randomization of Ultrasound Images](legacy/randomize/README.md)
- [Extraction of Raw Segmentation](legacy/compareimages/README.md#Extraction-of-Raw-Segmentation)
- [Evaluation Metrics for Segmentation](legacy/compareimages/README.md#Evaluation-Metrics)