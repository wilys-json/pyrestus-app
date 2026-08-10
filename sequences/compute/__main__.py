import argparse
from pathlib import Path
from src import compute_metric

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=str, metavar='INPUT',
                        help='input file')
    parser.add_argument('-m', '--measure', default='mlcs', type=str, metavar='MEASURE',
                        help='Regex patterns to look for.')
    args = parser.parse_args()

    input_file = Path(args.input)

    assert input_file.suffix in ['.csv', '.txt'], \
        "only accept .csv or .txt files"
    
    metric, output = compute_metric(args.input, args.measure, sep=' ')
    print(f"""
Output of {metric}:
{output}
""")
if __name__ == '__main__':
    main()
