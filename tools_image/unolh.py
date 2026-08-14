"""
This script decompresses .OLH files into one or more images.

It scans a specified directory for .OLH files, reads each file,
and saves the decompressed frames as PNG or BMP images. If an .OLH file contains
multiple frames, each frame is saved as a separate file with a
sequential suffix.
"""

import argparse
from pathlib import Path
from module.pc98_image.formats.olh import OLH

DEBUG = True


def main():
    """
    Finds and decompresses all .OLH files in a directory and saves them as images.
    """
    parser = argparse.ArgumentParser(description="Decompress .OLH files to images.")
    parser.add_argument(
        "-i",
        "--input-dir",
        type=Path,
        default=Path("./test"),
        help="Input directory containing .OLH files. Defaults to './test'.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("./test"),
        help="Output directory for the decompressed images. Defaults to './test'.",
    )
    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=["png", "bmp"],
        default="png",
        help="Output image format. Can be 'png' or 'bmp'. Defaults to 'png'.",
    )

    args = parser.parse_args()

    if DEBUG:
        args.input_dir = Path("c:/work_han/ozm/reference")
        args.output_dir = Path("c:/work_han/ozm/output")
        args.format = "png"

    # Ensure the output directory exists.
    args.output_dir.mkdir(exist_ok=True)

    # Find all .OLH files in the base directory.
    for file in args.input_dir.glob("*.OLH"):
        print(f"Processing {file.name}...")
        olh = OLH()
        olh.read_olh(file)

        # Process each frame found in the OLH file.
        for i, frame in enumerate(olh.frames):
            # If there is only one frame, use the original filename.
            # Otherwise, append a frame number to the filename.
            if len(olh.frames) == 1:
                out_name = f"{file.stem}.{args.format}"
            else:
                out_name = f"{file.stem}_{i}.{args.format}"

            out_path = args.output_dir / out_name

            # Save the decompressed frame in the specified format.
            if args.format == "png":
                olh.save_frame_as_png(i, out_path)
            elif args.format == "bmp":
                olh.save_frame_as_bmp(i, out_path)


if __name__ == "__main__":
    main()
