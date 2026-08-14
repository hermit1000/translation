import cv2
import json
from PIL import Image
from pathlib import Path
from module.name_db import NameDB
from module.font_table import FontTable
from module.font_image import imread_korean, return_img_roi_1byte, set_2byte_merge, set_font


def main():
    base_dir = Path("c:/work_han/font_update_db")
    font_name = "비스코"  # "둥근모", "비스코"
    if font_name == "둥근모":
        font_file = "ThinDungGeunMo.bmp"
    if font_name == "비스코":
        font_file = "BISCO.bmp"

    font_table = FontTable(Path("font_table/font_table-jpn.json"))
    src_font_canvas_path = base_dir / font_file
    src_font_canvas = cv2.imread(str(src_font_canvas_path), cv2.IMREAD_GRAYSCALE)

    # 1byte font
    input_cand_1byte = []
    input_cand_1byte += ["|고"]
    input_cand_1byte += ["|나", "|노"]
    input_cand_1byte += ["|다"]
    input_cand_1byte += ["|루"]
    input_cand_1byte += ["|마", "|모", "|미"]
    input_cand_1byte += ["|바"]
    input_cand_1byte += ["|시"]
    input_cand_1byte += ["|야", "|이"]
    input_cand_1byte += ["|조", "|즈", "|지", "|치"]
    input_cand_1byte += ["|케", "|쿠", "|키", "|타", "|토"]
    input_cand_1byte.sort()
    if len(input_cand_1byte) > 58:
        print(len(input_cand_1byte))
        return

    input_cand_1byte = []  # Remove 1byte code due to taikou1 font issue

    start_code_int = 0xA6
    ret_code_dict = {letter: f"{start_code_int + i:02X}" for i, letter in enumerate(input_cand_1byte)}

    for i, letter in enumerate(input_cand_1byte):
        roi = return_img_roi_1byte(hex(start_code_int + i))
        font_path = base_dir / "byte1" / f"{letter.replace('|', '')}.bmp"
        if not font_path.exists():
            print(f"{font_path} does not exist.")
            continue
        kor_font = imread_korean(font_path)
        src_font_canvas[roi[0] : roi[1], roi[2] : roi[3]] = kor_font

    letter_2byte = set()

    # Name
    db = NameDB()
    for _, korean_name, _ in db.iter_name_pairs("nb2"):
        family_name, given_name = korean_name.family, korean_name.given
        if len(family_name) > 6 or len(given_name) > 4:
            print(korean_name)
            continue

        for name in (family_name, given_name):
            pair_length = len(name) - len(name) % 2
            for i in range(0, pair_length, 2):
                letter_2byte.add(name[i : i + 2])

    # Add
    letter_2byte.add("가을")
    letter_2byte.add("겨울")
    letter_2byte.add("나카")
    letter_2byte.add("리쿠")
    letter_2byte.add("무라")
    letter_2byte.add("사키")
    letter_2byte.add("스미")
    letter_2byte.add("시로")
    letter_2byte.add("시모")
    letter_2byte.add("야마")
    letter_2byte.add("엔랴")
    letter_2byte.add("여름")
    letter_2byte.add("오오")
    letter_2byte.add("오카")
    letter_2byte.add("이와")
    letter_2byte.add("츠케")
    letter_2byte.add("쿠지")
    letter_2byte.add("호쿠")
    letter_2byte.add("후쿠")

    # Remove pairs that can be represented entirely with 1-byte fonts.
    letter_1byte = {letter.removeprefix("|") for letter in input_cand_1byte}

    def can_use_1byte(pair: str) -> bool:
        if len(pair) != 2:
            return False

        first, second = pair
        if first == "_":
            return second in letter_1byte
        if second == "_":
            return first in letter_1byte
        return first in letter_1byte and second in letter_1byte

    letter_2byte = {pair for pair in letter_2byte if not can_use_1byte(pair)}
    letter_2byte = list(letter_2byte)
    letter_2byte.sort()
    print(len(letter_2byte))

    start_code = "9540"  # 鼻
    input_cand = []
    input_cand.append(["은", font_name])
    input_cand.append(["는", font_name])
    input_cand.append(["이", font_name])
    input_cand.append(["가", font_name])
    input_cand.append(["을", font_name])
    input_cand.append(["를", font_name])
    input_cand.append(["와", font_name])
    input_cand.append(["과", font_name])
    input_cand.append(["에", font_name])
    input_cand.append(["의", font_name])
    code_dict, next_code = set_font(base_dir, font_table, src_font_canvas, start_code, 1, input_cand)
    ret_code_dict |= code_dict

    # set 4byte letters
    input_cand = []
    input_cand.append(["다이묘", font_name])
    input_cand.append(["와-과", font_name])
    input_cand.append(["은-는", font_name])
    input_cand.append(["을-를", font_name])
    input_cand.append(["이-가", font_name])

    input_cand.append(["나가토", font_name])
    input_cand.append(["도토미", font_name])
    input_cand.append(["도호쿠", font_name])
    input_cand.append(["리쿠츄", font_name])
    input_cand.append(["무사시", font_name])
    input_cand.append(["미카와", font_name])
    input_cand.append(["사누키", font_name])
    input_cand.append(["사츠마", font_name])
    input_cand.append(["사카이", font_name])
    input_cand.append(["스루가", font_name])
    input_cand.append(["시나노", font_name])
    input_cand.append(["시코쿠", font_name])
    input_cand.append(["야마토", font_name])
    input_cand.append(["오와리", font_name])
    input_cand.append(["와카사", font_name])
    input_cand.append(["에치고", font_name])
    input_cand.append(["에치젠", font_name])
    input_cand.append(["이나바", font_name])
    input_cand.append(["이즈모", font_name])
    input_cand.append(["이즈미", font_name])
    input_cand.append(["츄고쿠", font_name])
    input_cand.append(["치쿠히", font_name])
    input_cand.append(["코즈케", font_name])
    input_cand.append(["타지마", font_name])
    input_cand.append(["하리마", font_name])
    input_cand.append(["호우키", font_name])
    input_cand.append(["히타치", font_name])

    code_dict, next_code = set_font(base_dir, font_table, src_font_canvas, next_code, 2, input_cand)
    ret_code_dict |= code_dict

    # Set merged 2byte letters
    letter_2byte = [[s, "default"] for s in letter_2byte]  # Change format
    code_dict, _ = set_2byte_merge(base_dir, letter_2byte, font_table, src_font_canvas)
    ret_code_dict |= code_dict

    # Save font canvas image
    dst_font_canvas_path = base_dir / f"nobu2-{font_file}"
    pil_img = Image.fromarray(src_font_canvas)
    one_bit_img = pil_img.convert("1")
    one_bit_img.save(dst_font_canvas_path)
    with open(base_dir / "custom_word.json", "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(ret_code_dict, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
