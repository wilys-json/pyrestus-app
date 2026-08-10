import argparse
import yaml
from tqdm_batch import batch_process
from pathlib import Path
from src import SKIP

def _make_skip_animation(input_file, config, output_dir='output', trim_pth=1, video_format='mp4', **kwargs):
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    output_pth = output_dir / f"{'-'.join(Path(input_file).parts[trim_pth:])}.{video_format}"
    profiler = SKIP(input_file, config)
    profiler.animate(output_pth)
    return

def make_skip_animation(input_folder, config_file, source_file_depth=2, n_workers=8, **kwargs):
    files = list(Path(input_folder).glob("/".join("*" for _ in range(source_file_depth))))
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    batch_process(files, _make_skip_animation,
                  config=config,
                  n_workers=n_workers,
                  sep_progress=True,
                  **kwargs)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_folder', type=str,
                        help='Folder containing annotation zip files.')
    parser.add_argument('config_file', type=str, default='skip.yml',
                        help='Config file in YML format')
    parser.add_argument('--output_config', '-o', type=str, default='output_config.yml',
                        help='Directory for outputs. Default: `output.config')
    
    args = parser.parse_args()
    
    with open(args.output_config, 'r') as file:
        output_config = yaml.safe_load(file)
    make_skip_animation(args.input_folder, args.config_file, **output_config)

if __name__ == "__main__":
    main()

