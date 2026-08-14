import sys
import cv2
import numpy as np
from pathlib import Path


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
    src_fnt_path = Path("C:/work_han/font_dosjp/JIS.FNT")

    font_dict = load_to_dictionary(base_dir / f"{font_name}.tbl")
    font_bin_path = base_dir / f"{font_name}.bin"
    save_path = base_dir / f"{font_name}.fnt"

    with open(font_bin_path, "rb") as f:
        bin_data = bytearray(f.read())
    with open(src_fnt_path, "rb") as f:
        src_bin_data = bytearray(f.read())

    if DEBUG:
        address = font_dict.get(get_cp_949_code("힝"))
        if address is None:
            raise ValueError("가 not found in font dictionary.")
        address = int(address, 16)
        bin = bin_data[address : address + 32]

        address = 0xBE40  # 가
        address = 0x1E3E0  # 힝
        bin = src_bin_data[address : address + 32]

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
        address_sta = int(font_dict.get(get_cp_949_code("가")), 16)
        address_end = int(font_dict.get(get_cp_949_code("힝")), 16)
        bin = bin_data[address_sta : address_end + 32]

        src_address_sta = 0xBE40  # 가
        src_address_end = 0x1E3E0  # 힝
        src_bin_data[src_address_sta : src_address_end + 32] = bin

        with open(save_path, "wb") as f:
            f.write(src_bin_data)


if __name__ == "__main__":
    main()
