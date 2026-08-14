"""
This script validates the colors of a PNG image against a provided color palette.

It performs the following checks:
1.  Loads a palette file (e.g., in .rgb format).
2.  Inspects the palette for properties like the total number of colors and identifies any duplicates.
3.  Loads a PNG image and extracts its unique colors.
4.  Compares the PNG's colors against the palette's colors.
5.  Reports any colors found in the PNG that are not present in the palette.

This is useful for ensuring that an image adheres to the color limitations of a specific system or format.
"""
import sys
import os
from module.pc98_image.palette import Palettes

try:
    from PIL import Image
except ImportError:
    print(
        "Pillow library not found. Please install it with 'pip install Pillow'",
        file=sys.stderr,
    )
    sys.exit(1)


# --- Configuration ---
# DEBUG mode allows running the script with hardcoded file paths for quick testing.
# Set to False to use command-line arguments.
DEBUG = True


def validate_png_colors(png_path: str, palette_path: str) -> None:
    """
    Checks if a PNG file contains any colors that are not in the provided palette.
    Also provides details about the palette itself.

    Args:
        png_path (str): The file path of the PNG image to validate.
        palette_path (str): The file path of the palette file (e.g., .rgb).
    """
    print(f"Validating colors in '{png_path}' against palette '{palette_path}'...")

    # 1. Load the external palette
    if not os.path.exists(palette_path):
        print(f"Error: Palette file not found: {palette_path}", file=sys.stderr)
        return

    palette_obj = Palettes(palette_path, order="rgb")
    if not palette_obj.palettes:
        print(f"Error: Could not load palette from {palette_path}", file=sys.stderr)
        return

    # --- Palette Inspection ---
    palette_list = palette_obj.palettes[0]
    print(f"\n--- Palette Inspection ('{palette_path}') ---")
    print(f"Total color entries read from palette: {len(palette_list)}")

    # Print the full list of colors to identify duplicates
    print("Palette color entries:")
    for i, color in enumerate(palette_list):
        print(f"  Index {i:2d} (0x{i:X}): {color}")

    allowed_colors_set = set(palette_list)
    print(f"Number of UNIQUE colors in palette: {len(allowed_colors_set)}")
    if len(palette_list) != len(allowed_colors_set):
        print("NOTE: The palette contains duplicate color entries.")

    print("-" * 20)

    # 2. Load the PNG and get its unique colors
    if not os.path.exists(png_path):
        print(f"Error: PNG file not found: {png_path}", file=sys.stderr)
        return

    img = Image.open(png_path).convert("RGB")

    try:
        # getcolors() is faster but may fail if the image has too many colors.
        png_colors = img.getcolors(img.width * img.height)
        png_colors_set = {color for count, color in png_colors} if png_colors else set()
    except Exception as e:
        print(
            f"Could not get colors from PNG, possibly too many unique colors. Error: {e}",
            file=sys.stderr,
        )
        print("Falling back to slower pixel-by-pixel iteration...")
        # Fallback for images with more than maxcolors.
        png_colors_set = {pix for pix in img.getdata()}


    print("\n--- PNG Color Validation ---")
    print(f"Found {len(png_colors_set)} unique colors in '{png_path}'.")

    # 3. Compare the sets to find any unsupported colors
    unsupported_colors = png_colors_set - allowed_colors_set

    if not unsupported_colors:
        print("\nSUCCESS: All colors in the PNG are supported by the palette.")
    else:
        print(
            f"\nFAILURE: Found {len(unsupported_colors)} unsupported color(s) in the PNG."
        )
        print("These colors are present in the image but not in the palette file:")
        for i, color in enumerate(sorted(list(unsupported_colors))):
            if i >= 20:
                print(f"  ... and {len(unsupported_colors) - i} more.")
                break
            print(f"  - {color}")


if __name__ == "__main__":
    if not DEBUG:
        # Standard execution using command-line arguments.
        if len(sys.argv) != 3:
            print(
                "Usage: python validate_colors.py <input.png> <palette.rgb>",
                file=sys.stderr,
            )
            sys.exit(1)

        png_file = sys.argv[1]
        palette_file = sys.argv[2]
    else:
        # Debug execution with hardcoded file paths.
        # This is useful for development and quick tests.
        png_file = "c:/work_han/ozm/ozm_files/title0.png"
        palette_file = "c:/work_han/ozm/ozm_files/title0.rgb"

    validate_png_colors(png_file, palette_file)
