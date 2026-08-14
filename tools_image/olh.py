"""
This script compresses PNG files into the OLH (Old Lion-head) image format.

It uses a reference OLH file to provide the necessary metadata for compression,
such as the palette and image dimensions. The script processes all PNG files
in a given input directory, finds their corresponding reference OLH files in
another directory, and saves the compressed output to a specified output
directory.
"""

import argparse
from pathlib import Path
from module.pc98_image.formats.olh import OLH


DEBUG = True


def main():
    """
    Parses command-line arguments and processes PNG files for OLH compression.
    """
    if not DEBUG:
        parser = argparse.ArgumentParser(description="Compress PNG files to OLH format using a reference OLH file.")
        parser.add_argument("--input-dir", type=Path, required=True, help="Directory with input PNG files.")
        parser.add_argument(
            "--ref-dir",
            type=Path,
            required=True,
            help="Directory with reference OLH files.",
        )
        parser.add_argument(
            "--output-dir",
            type=Path,
            required=True,
            help="Directory to save output OLH files.",
        )
        args = parser.parse_args()

        input_dir = args.input_dir
        ref_dir = args.ref_dir
        output_dir = args.output_dir
    else:
        input_dir = Path("c:/work_han/ozm/output")
        ref_dir = Path("c:/work_han/ozm/reference")
        output_dir = Path("c:/work_han/ozm/output")

    # Ensure the output directory exists.
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process each PNG file in the input directory.
    for file in input_dir.glob("*.png"):
        print(file.name)
        relative_path = file.relative_to(input_dir)

        # Determine the paths for the reference and output files.
        ref_path = ref_dir / relative_path.with_suffix(".OLH")
        out_path = output_dir / relative_path.with_suffix(".OLH")

        # Skip if the output file already exists.
        if out_path.exists():
            continue

        # Skip if the reference file does not exist.
        if not ref_path.exists():
            print(f"Reference file {ref_path} not found for {file.name}. Skipping.")
            continue

        print(f"Processing {file.name}...")

        # Initialize the OLH object and read the reference file.
        olh = OLH()
        olh.read_olh(ref_path)

        # Ensure the reference OLH file contains at least one frame.
        if not olh.frames:
            print(f"No frames found in reference OLH {ref_path}. Skipping.")
            continue

        # Convert the input PNG to 8bpp indexed color data.
        olh.read_png_as_8bpp(file)

        # Create the parent directory for the output file if it doesn't exist.
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Compress the data and save it to the output file.
        olh.compress(out_path, save_size=True, save_palette=True)
        print(f"  Saved to {out_path}")


if __name__ == "__main__":
    main()
