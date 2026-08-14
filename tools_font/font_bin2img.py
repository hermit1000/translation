import sys
import cv2
import numpy as np

from PIL import Image
from pathlib import Path
from module.font_image import return_img_roi
from module.font_table import FontTable


def get_cp_949_code(letter):
    """
    Encodes a single character into its CP949 hexadecimal representation.
    """
    try:
        # Encode the character to CP949 bytes
        cp949_bytes = letter.encode("cp949")
        # Convert bytes to a hexadecimal string
        hex_code = "".join([f"{byte:02X}" for byte in cp949_bytes])
        return hex_code
    except UnicodeEncodeError:
        print(f"Error: '{letter}' cannot be encoded to CP949.")
        return None


def load_to_dictionary(file_path):
    """
    Loads a text file with "code,address" lines into a dictionary.

    Args:
        file_path (str): The path to the input text file.

    Returns:
        dict: A dictionary where keys are codes and values are addresses.
              Returns an empty dictionary if the file is not found or empty.
    """
    data_dict = {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue

                parts = line.split(",")
                if len(parts) == 2:
                    code = parts[0].strip()
                    address = parts[1].strip()
                    data_dict[code] = address
                else:
                    print(f"Warning: Skipping malformed line {line_num} in {file_path}: '{line}'")
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}", file=sys.stderr)
    except Exception as e:
        print(f"An error occurred while reading the file: {e}", file=sys.stderr)
    return data_dict


def main():
    DEBUG = False

    font_name = "ThinDungGeunMo_cp949_full"
    base_dir = Path("c:/work_han/font_")

    font_dict = load_to_dictionary(base_dir / f"{font_name}.tbl")
    font_bin_path = base_dir / f"{font_name}.bin"
    save_path = base_dir / f"{font_name}.bmp"
    with open(font_bin_path, "rb") as f:
        bin_data = bytearray(f.read())

    if DEBUG:
        code = get_cp_949_code("가")
        address = font_dict.get(code)
        if address is None:
            raise ValueError(f"Code '{code}' not found in font dictionary.")
        address = int(address, 16)
        bin = bin_data[address : address + 32]
        bits = np.unpackbits(np.frombuffer(bin, dtype=np.uint8))
        bits = 1 - bits
        img = bits.reshape((16, 16)) * 255

        scale_factor = 4
        width = int(img.shape[1] * scale_factor)
        height = int(img.shape[0] * scale_factor)
        dim = (width, height)

        # Resize image using nearest-neighbor interpolation to keep pixels sharp
        img_resized = cv2.resize(img, dim, interpolation=cv2.INTER_NEAREST)
        cv2.imshow("Image", img_resized)
        cv2.waitKey(0)
    else:
        src_font_bmp_path = Path("c:/work_han/anex86.bmp")
        src_font_table_path = Path("font_table/font_table-kor-convert.json")
        img_dst = cv2.imread(src_font_bmp_path, 0)
        dst_font_table = FontTable(src_font_table_path)

        char_list = dst_font_table.char2code.keys()
        for letter in char_list:
            code = get_cp_949_code(letter)
            address = font_dict.get(code)
            if address is None:
                continue

            # Get font
            address = int(address, 16)
            bin = bin_data[address : address + 32]
            bits = np.unpackbits(np.frombuffer(bin, dtype=np.uint8))
            bits = 1 - bits
            img = bits.reshape((16, 16)) * 255

            # Paste font
            dst_code = dst_font_table.get_code(letter)
            roi_dst = return_img_roi(dst_code, DEBUG)
            img_dst[roi_dst[0] : roi_dst[1], roi_dst[2] : roi_dst[3]] = img
        img_pil = Image.fromarray(img_dst).convert("1")
        img_pil.save(save_path)


if __name__ == "__main__":
    main()
