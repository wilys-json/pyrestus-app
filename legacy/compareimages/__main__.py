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

import argparse
import sys
import numpy as np
import pandas as pd
from tqdm import tqdm
from pathlib import Path
from datetime import datetime
from tqdm_batch import batch_process
from joblib import cpu_count
from src import (contains_dir, make_hyperlink, aggregate,
                 make_rater_dataframe, make_raters_dataframe,
                 get_segmentation_mask, dice_scores, hausdorff_distances)


OUTPUT_DIR = 'outputs'

def debug(df: pd.DataFrame, timestamp:str):
    debug_log_dir = Path('.log')
    if not debug_log_dir.is_dir():
        debug_log_dir.mkdir()
    df.to_html((debug_log_dir / f'DataFrame-{timestamp}.html'))


def make_dataframe(args: argparse.Namespace) -> pd.DataFrame:
    input_dir = Path(args.inputFolder)
    if args.repeated_image:
        args.ignore_inconsistent_name = True
        args.ignore_error = True
        match_file_type = Path(args.repeated_image).suffix
        assert match_file_type == '.csv', \
            f"""Must provide .csv file for repeated image Dice.\n
                {match_file_type} file was provided."""
        df = pd.read_csv(args.repeated_image, header=args.csv_header)
        df = df.applymap(lambda x: (input_dir / x))
        indices = []
        for row in df.itertuples():
            idx, file1, file2 = row
            indices += ['-'.join([file1.name, file2.name])]
        df = df.set_index(np.array(indices))

    else:
        if contains_dir(args.inputFolder):
            df = make_raters_dataframe(args.inputFolder)
        else:
            df = make_rater_dataframe(args.inputFolder)

    return df


def generate_mask(df: pd.DataFrame, args: argparse.Namespace, **kwargs):
    print(f"Generating segmentation mask from {args.inputFolder}...")

    # Parallel processing
    batch_process(df.stack().values, get_segmentation_mask,
                  n_workers = cpu_count(),
                  sep_progress=True, save=True,
                  show_original=args.show_original,
                  show_binary=args.show_binary,
                  show_mask=args.show_mask,
                  lines_only=args.lines_only,
                  timestamp=kwargs.get('timestamp'),
                  output_dir=kwargs.get('output_dir'),
                  color=args.color,
                  cropping=args.cropping,
                  correct=args.correction)
    """
    # Iterative processing
    df.progress_applymap(
        lambda x: get_segmentation_mask(str(x), save=True,
                                      show_original=args.show_original,
                                      show_binary=args.show_binary,
                                      show_mask=args.show_mask,
                                      lines_only=args.lines_only,
                                      timestamp=kwargs.get('timestamp'),
                                      output_dir=kwargs.get('output_dir')))
    """
    print(f"{df.size} segmentation masks generated in {kwargs.get('output_dir')}.")


def calculate_dice_score(df: pd.DataFrame, args: argparse.Namespace, **kwargs):
    timestamp = kwargs.get('timestamp')
    output_dir = kwargs.get('output_dir') / f"Dice-{timestamp}"
    output_dir.mkdir()

    print(f"Calculating Dice coefficients from data in {args.inputFolder}...")
    image_wise_dice, average_dice, hyperlink_df = dice_scores(df,
                ignore_error=args.ignore_error,
                shape_only=args.compare_shape_only,
                repeated_image=args.repeated_image,
                ignore_inconsistent_name=args.ignore_inconsistent_name,
                output_dir=output_dir,
                create_overlapping_image=args.create_overlaps)


    image_wise_html = output_dir / f"Image-Wise-Dice-{timestamp}.html"
    average_html = output_dir / f"Average-Dice-{timestamp}.html"
    descriptive_html = output_dir / f"Image-Wise-DescriptiveStats-{timestamp}.html"

    if not hyperlink_df is None:
        hyperlink_df.to_html(image_wise_html, escape=False)
    else:
        image_wise_dice.to_html(image_wise_html)

    average_dice.to_html(average_html)
    descriptive_dice = aggregate(image_wise_dice)
    descriptive_dice.to_html(descriptive_html)

    print(f"Dice coefficient results have been saved to: \
            {image_wise_html}, {average_html}, {descriptive_html}.")


def calculate_hausdorff_distance(df: pd.DataFrame, args: argparse.Namespace,
                                 **kwargs):
    print(f"Calculating Hausdorff Distance from data in {args.inputFolder}...")
    timestamp = kwargs.get('timestamp')
    output_dir = kwargs.get('output_dir') / f"Hausdorff_Distance_{timestamp}"
    output_dir.mkdir()
    dropped_columns_message = None
    tolerance = (None if args.tolerance == 0
                else (args.tolerance, args.tolerance_dim))
    image_wise_hausdorff, hyperlink_df = hausdorff_distances(df,
                            extraction_method=args.method,
                            ignore_error=args.ignore_error,
                            point_threshold=args.point_threshold,
                            repeated_image=args.repeated_image,
                            output_dir=output_dir,
                            create_overlapping_image=args.create_overlaps,
                            tolerance=tolerance,
                            average=args.average,
                            balanced=args.balanced)

    image_wise_hd_html = output_dir / f"Image-Wise-Hausdorff-Distance-{timestamp}.html"
    zero_values = (image_wise_hausdorff == -1.0).any(axis=1)

    if not hyperlink_df is None:
        hausdorff_table = hyperlink_df.to_html(escape=False)
    else:
        hausdorff_table = image_wise_hausdorff.to_html()


    if not zero_values.all():
        dropped_columns_message = ', '.join(image_wise_hausdorff[zero_values].index)
        image_wise_hausdorff = image_wise_hausdorff[~zero_values]


    summary_hd_html = output_dir / f"Hausdorff-Distance-Summary-{timestamp}.html"
    summary_df = aggregate(image_wise_hausdorff)
    hausdorff_summary = summary_df.to_html()

    if dropped_columns_message:
        hausdorff_table += f"<h4>Note: Unable to calculate Hausdorff Distance for the following images: {dropped_columns_message}. -1 was assigned to the comparison.</h4>"
        hausdorff_summary += f"<h4>Note: The following images were excluded: {dropped_columns_message}.</h4>"

    with open(image_wise_hd_html, 'w') as image_wise:
        image_wise.write(hausdorff_table)
        image_wise.close()

    with open(summary_hd_html, 'w') as summary:
        summary.write(hausdorff_summary)
        summary.close()

    print(f"Hausdorff Distance results have been saved to: \
            {image_wise_hd_html} & {summary_hd_html}.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('inputFolder', type=str, nargs='?', default='')
    parser.add_argument('--generate-mask', dest='function', action='store_const',
                        const='generate_mask', default='')
    parser.add_argument('-r', '--show-original', action='store_true',
                        default=False)
    parser.add_argument('-b', '--show-binary', action='store_true',
                        default=False)
    parser.add_argument('-m', '--show-mask', action='store_true',
                        default=False)
    parser.add_argument('-l', '--lines-only', action='store_true',
                        default=False)
    parser.add_argument('--ignore-error', action='store_true',
                        default=False)
    parser.add_argument('--ignore-inconsistent-name', action='store_true',
                        default=False)
    parser.add_argument('--calculate-dice-score', action='store_const',
                        dest='function', const='calculate_dice_score',
                        default='')
    parser.add_argument('--repeated-image', type=str, default='')
    parser.add_argument('--csv-header', type=int, default=0)
    parser.add_argument('--debug', action='store_true', default=False)
    parser.add_argument('--calculate-hausdorff-distance',  action='store_const',
                        dest='function', const='calculate_hausdorff_distance',
                        default='')
    parser.add_argument('--point-threshold', type=int, default=20)
    parser.add_argument('--compare-shape-only', action='store_true',
                        default=False)
    parser.add_argument('--create-overlaps', action='store_true',
                        default=False)
    parser.add_argument('--tolerance', type=int, default=0)
    parser.add_argument('--tolerate-1d', action='store_const',
                        dest='tolerance_dim', const='1d',
                        default='1d')
    parser.add_argument('--tolerate-2d', action='store_const',
                        dest='tolerance_dim', const='2d',
                        default='1d')
    parser.add_argument('--average', action='store_true',
                        default=False)
    parser.add_argument('--balanced', action='store_true', default=False)
    parser.add_argument('--thin', action='store_const', dest='method',
                        const='thin', default='thin')
    parser.add_argument('--canny', action='store_const', dest='method',
                        const='canny', default='thin')
    parser.add_argument('--contour', action='store_const', dest='method',
                        const='contour', default='thin')
    parser.add_argument('--raw-points', action='store_const', dest='method',
                        const='raw_points', default='thin')
    parser.add_argument('-o', '--output', type=str, default=OUTPUT_DIR)
    parser.add_argument('--no-cropping', action='store_false', dest='cropping',
                        default=True)
    parser.add_argument('-c', '--color', type=str, default=None)
    parser.add_argument('--no-correction', action='store_false', dest='correction',
                        default=True)


    args = parser.parse_args()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    functions = {
        "generate_mask" : generate_mask,
        "calculate_dice_score" : calculate_dice_score,
        "calculate_hausdorff_distance" : calculate_hausdorff_distance
    }

    if not args.inputFolder:
        print("""No input folders given.
         Usage: compaireimages $input_folder
          [--generate-mask] / [--calculate-dice-score] /
          [--calculate-hausdorff-distance]""")
        sys.exit(0)

    if not args.function:
        print("""You must select any of these functions:\n
         compaireimages $input_folder
         [--generate-mask] / [--calculate-dice-score] /
         [--calculate-hausdorff-distance]""")
        sys.exit(0)

    output_dir = Path(args.output)
    if not output_dir.is_dir():
        output_dir.mkdir(parents=True, exist_ok=True)

    df = make_dataframe(args)

    tqdm.pandas()

    if args.debug:
        debug(df, timestamp)

    functions[args.function](df, args, timestamp=timestamp,
                             output_dir=output_dir)


if __name__ == '__main__':
    main()
