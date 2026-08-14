import cv2
import numpy as np

from pathlib import Path
from typing import List, Dict, Set, Tuple

from module.font_table import FontTable


# Font image info
# Entire font image size = 2048x2048
# Font patch size = 16x16
# Font patch array size = 128x128


def return_img_roi(code_hex: str, debug=False) -> Tuple[int, int, int, int]:
    """
    Return the pixel ROI (row pixel start, row pixel end, column pixel start, column pixel end) based on the input font code

    Args:
    code_hex (str): A hexadecimal code as a string, e.g., "8140".

    Returns:
    Tuple[int, int, int, int]: Y start, Y end, X start, X end.
    """
    code = int(code_hex, 16)

    code_prefix = (code >> 8) & 0xFF
    code_suffix = code & 0xFF

    if debug:
        print(f"{code_prefix:X} {code_suffix:X}")

    # Set column (X)
    col = (code_prefix - 0x81) * 2 + 1
    col += 1 if code_suffix >= 0x9F else 0

    # Set row (Y)
    if code_suffix >= 0x9F:
        row = 33 + code_suffix - 0x9F
    else:
        row = 33 + code_suffix - 0x40
        if code_suffix >= 0x80:
            row -= 1

    # Set a patch ROI
    if debug:
        print(row, col)
    ypos = row * 16
    xpos = col * 16
    return [ypos, ypos + 16, xpos, xpos + 16]


def return_img_roi_1byte(code_hex: str, debug=False) -> Tuple[int, int, int, int]:
    """
    Return the pixel ROI (row pixel start, row pixel end, column pixel start, column pixel end) based on the input font code

    Args:
    code_hex (str): A hexadecimal code as a string, e.g., "8140".

    Returns:
    Tuple[int, int, int, int]: Y start, Y end, X start, X end.
    """
    code = int(code_hex, 16)
    if code > 0xFF or code < 0:
        raise ValueError(f"{code_hex} is not a supported range.")

    # col = code
    # row = 0

    # # Set a patch ROI
    # if debug:
    #     print(row, col)
    # ypos = row * 16
    # xpos = col * 8

    col = 20
    row = code - 128  # 32

    # Set a patch ROI
    if debug:
        print(row, col)

    ypos = row * 16
    xpos = col * 8

    return [ypos, ypos + 16, xpos, xpos + 8]


def imread_korean(path):
    img_array = np.fromfile(path, np.uint8)
    img = cv2.imdecode(img_array, 0)
    return img


def imwrite_korean(path, img, params=None):
    extension = path.split(".")[-1]
    res, img_encode = cv2.imencode(f".{extension}", img, params)
    if res:
        with open(path, "wb") as f:
            img_encode.tofile(f)
        return True
    return False


def crop_paste(img_src, img_dst, roi_src, roi_dst):
    img_dst[roi_dst[0] : roi_dst[1], roi_dst[2] : roi_dst[3]] = img_src[
        roi_src[0] : roi_src[1], roi_src[2] : roi_src[3]
    ]
    return img_dst


def add_text_pairs(text: str, pairs: Set[str]) -> bool:
    contains_space = False
    for i in range(0, len(text), 2):
        pair = text[i : i + 2]
        if " " in pair:
            contains_space = True
        if len(pair) == 1:
            pair += "_"
        pairs.add(pair)
    return contains_space


def draw_letters_on_canvas(
    font_canvas: np.ndarray,
    input_cands: List,
    img_path_dict: Dict,
    code_list: List[str],
    num_letters: int,
    need_merge=False,
) -> Dict[str, str]:
    code_idx = 0
    ret_dict_code = dict()

    # Update font canvas
    for korean, font_name in input_cands:
        if not need_merge:
            if korean not in img_path_dict[font_name]:
                code_idx += num_letters
                continue
            word_img = imread_korean(str(img_path_dict[font_name][korean]))
            code_tag = ""
            for i in range(num_letters):
                code = code_list[code_idx + i]
                roi = return_img_roi(code)
                font_canvas[roi[0] : roi[1], roi[2] : roi[3]] = word_img[0:16, 16 * i : 16 * i + 16]
                code_tag += code
            ret_dict_code[korean] = code_tag
            code_idx += num_letters
        else:  # Need to merge
            word_img = np.full((16, 16), 255, dtype=np.uint8)

            word_img[:, 0:8] = imread_korean(str(img_path_dict[font_name][korean[0]]))
            if korean[1] != "_":
                word_img[:, 8:] = imread_korean(str(img_path_dict[font_name][korean[1]]))

            code = code_list[code_idx]
            roi = return_img_roi(code)
            font_canvas[roi[0] : roi[1], roi[2] : roi[3]] = word_img
            code_idx += 1
            ret_dict_code[korean] = code

    return ret_dict_code, code_idx


def set_font(
    base_dir: Path,
    font_table: FontTable,
    src_font_canvas: np.ndarray,
    start_code: str,
    num_letters: int,
    input_cands: list,
):
    img_db = dict()
    num_bytes = num_letters * 2

    for korean, font_name in input_cands:
        if font_name in img_db:
            continue
        img_db[font_name] = dict()
        font_dir = f"byte{num_bytes}" if font_name == "default" else f"byte{num_bytes}{font_name}"
        for letter_path in (base_dir / font_dir).rglob("*.bmp"):
            img_db[font_name][letter_path.stem] = letter_path

    for korean, font_name in input_cands:
        if korean not in img_db[font_name]:
            print(f"{korean} - no font")

    code_list = list(font_table.code2char.keys())
    code_idx = code_list.index(start_code)
    code_list = code_list[code_idx:]

    ret_dict_code, next_code_idx = draw_letters_on_canvas(
        font_canvas=src_font_canvas,
        input_cands=input_cands,
        img_path_dict=img_db,
        code_list=code_list,
        num_letters=num_letters,
    )

    next_code = code_list[next_code_idx]
    return ret_dict_code, next_code


def set_2byte_merge(
    base_dir: Path,
    input_cand_2byte: list,
    font_table: FontTable,
    src_font_canvas: np.ndarray,
    start_code: str = "959F",
):
    img_db_1byte = {
        "default": dict(),
    }
    for letter_path in (base_dir / "byte1").rglob("*.bmp"):
        img_db_1byte["default"][letter_path.stem] = letter_path

    code_list = list(font_table.code2char.keys())
    code_idx = code_list.index(start_code)
    code_list = code_list[code_idx:]

    ret_dict_code, next_code_idx = draw_letters_on_canvas(
        font_canvas=src_font_canvas,
        input_cands=input_cand_2byte,
        img_path_dict=img_db_1byte,
        code_list=code_list,
        num_letters=1,
        need_merge=True,
    )

    next_code = code_list[next_code_idx]
    return ret_dict_code, next_code
