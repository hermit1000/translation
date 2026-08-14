"""
This script compresses PNG files into the OZM image format.

It searches for PNG files in a target directory, and for each PNG, it finds a
corresponding reference .OZM file in a separate directory. It then uses the
reference file's metadata to compress the new PNG into the OZM format,
saving the output in the same directory as the input PNG.
"""

from pathlib import Path
from module.pc98_image.formats.ozm import OZM


def main():
    """
    Finds and compresses PNG files into OZM format using reference OZM files.
    """
    # --- Configuration ---
    # It is recommended to replace these hardcoded paths with command-line arguments
    # for better flexibility.
    ref_base_dir = Path("../ozm/m2")
    target_dir = Path("../ozm/m2_kor")
    # --- End Configuration ---

    # Recursively find all PNG files in the target directory.
    for file in target_dir.rglob("*.png"):
        relative_path = file.relative_to(target_dir)

        # Define the output path for the compressed OZM file.
        out_path = target_dir / relative_path.with_suffix(".OZM")
        # Skip if the output file already exists.
        if out_path.exists():
            continue

        # Determine the path to the corresponding reference file.
        target_path = ref_base_dir / relative_path.with_suffix(".OZM")
        if not target_path.exists():
            print(f"Reference file {target_path.name} does not exist. Skipping.")
            continue

        print(f"Processing {file.name}...")

        # Initialize the OZM object and read the reference file.
        ozm = OZM()
        ozm.read_ozm(target_path)
        # Read the pixel data from the input PNG.
        ozm.read_png_as_8bpp(file)

        # Example of writing the raw 8bpp data to a file for debugging.
        # with open("TITLE.raw", "wb") as f:
        #     f.write(ozm.data_8bpp)

        # Compress the data and save it to the output file.
        ozm.compress(out_path)
        print(f"  Saved to {out_path}")


if __name__ == "__main__":
    main()
