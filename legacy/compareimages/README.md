# Segmentation Extraction & Evaluation

This module offers basic functionalities for extracting raw segmentations performed in common photo editing softwares in the command line interface (CLI) - for annotations resulting in other formats like .xml from CVAT, please use the `annotation` module (coming soon). The target `inputFolder` shall follow this file structure:

```
target_main_folder
├──annotator_1
│   ├──image_00_by_annotator_1.png
│   ├──image_01_by_annotator_1.png
│   ├──image_02_by_annotator_1.png
│   └── ...
├──annotator_2
│   ├──image_00_by_annotator_2.png
│   ├──image_01_by_annotator_2.png
│   ├──image_02_by_annotator_2.png
│   └── ...
└──annotator_n
    ├──image_00_by_annotator_n.png
    ├──image_01_by_annotator_n.png
    ├──image_02_by_annotator_n.png
    └── ...
```

## Extraction of Raw Segmentation
  To extract segmentations, open the CLI (e.g. Terminal in MacOS) and type:

  ```
  python3 compareimages path/to/segmentations --generate-mask
  ```

#### Option flags

`-r`, `--show-original` - the original segmentation will be shown during extraction (default: disabled)


`-b`, `--show-binary` - the extraction will be shown as a binary image (default: disabled)


`-l`, `--lines-only` - only extract contours / lines from segmentation; otherwise, a flood fill method will be applied to the segmentation (default: disabled)


`-m`, `--show-mask` - show the final extraction mask (default:disabled)


`-o`, `--output` `path/to/output/directory` - the output directory (default: `outputs`)




## Evaluation Metrics

This submodule allows the user to evaluate reliability / similarity of segmentations using Dice coefficient and Hausdorff distance. Depending on the research context, the use of dice coefficient is always always recommended for closed shapes, while Hausdorff distance for open shapes or contours.

##### Common option flags

`--ignore-error` - ignore any inconsistencies in image dimension, resulting in NaN or -1.0 values. (default: disabled)


`--ignore-inconsistent-name` - ignore any file name inconsistency, such that the program will run through all instances in an exhaustive pairwise manner. (default: disabled)

`--repeated-image` - used for intra-rater reliability / re-rating checking (default: disabled)

`--create-overlaps` - overlapped images of the segmentations will be created in the `--output` folder (default: disabled)

#### Dice coefficient

Calculating the pairwise dice coefficient in all segmentation pairs in the target folder.
Command:

```
python3 compareimages path/to/extracted/segmentation --calculate-dice-score
```

#### Hausdorff distance

Calculating the pairwise Hausdorff distance in all segmentation pairs in the target folder.

```
python3 compareimages path/to/extracted/segmentation --calculate-hausdorff-distance
```
