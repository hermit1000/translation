"""
This script decompresses .OZM files (in OZM format) into PNG images.

It recursively finds all .OZM files in a specified base directory,
decompresses them using the OZM library, and saves the output as PNG files
in a target directory. The script includes functionality to skip certain
files based on predefined lists.
"""

from pathlib import Path
from module.pc98_image.formats.ozm import OZM


def main():
    """
    Finds and decompresses all .OZM files in the base directory and saves them as PNGs.
    """
    # --- Configuration ---
    # It is recommended to replace these hardcoded paths with command-line arguments
    # for better flexibility.
    base_dir = Path("../ozm/output")
    out_base_dir = Path("../ozm/output")
    # --- End Configuration ---

    # Ensure the output directory exists.
    out_base_dir.mkdir(parents=True, exist_ok=True)

    osm = OZM()
    # Recursively find all files with the .OZM extension in the base directory.
    for file in base_dir.glob("*.OZM"):
        # Define the output path for the decompressed PNG file.
        out_name = file.name.replace(".OZM", ".png")
        out_path = out_base_dir / out_name

        # Skip the file if it has already been decompressed.
        if out_path.exists():
            continue

        print(f"Processing {file.name}...")

        # Read and decompress the OZM file.
        if not osm.read_ozm(file, "rgb"):
            print(f"  Failed to read {file.name}. Skipping.")
            continue
        osm.decompress()

        # Save the decompressed data as a PNG image.
        osm.save_as_png(out_path)
        print(f"  Saved to {out_path}")


if __name__ == "__main__":
    main()
