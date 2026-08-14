import cv2
import json
from PIL import Image
from pathlib import Path
from module.name_db import NameDB
from module.font_table import FontTable
from module.font_image import add_text_pairs, set_2byte_merge, set_font


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

    letter_2byte = set()

    # Name
    db = NameDB()
    for _, korean_name, _ in db.iter_name_pairs("taiko2"):
        family_name, given_name = korean_name.family, korean_name.given
        if len(family_name) > 6 or len(given_name) > 6:
            print(korean_name)
            continue

        if len(family_name) % 2:
            family_name += "_"
        if len(given_name) % 2:
            given_name = "_" + given_name

        add_text_pairs(family_name, letter_2byte)
        add_text_pairs(given_name, letter_2byte)

    # 추가
    letter_2byte.add("미마")
    letter_2byte.add("사노")
    letter_2byte.add("시키")

    letter_2byte = list(letter_2byte)
    letter_2byte.sort()
    print(len(letter_2byte))

    ret_code_dict = {}
    start_code = "9540"  # 鼻
    input_cand = []
    input_cand.append(["은", "비스코"])
    input_cand.append(["는", "비스코"])
    input_cand.append(["이", "비스코"])
    input_cand.append(["가", "비스코"])
    input_cand.append(["을", "비스코"])
    input_cand.append(["를", "비스코"])
    input_cand.append(["와", "비스코"])
    input_cand.append(["과", "비스코"])
    input_cand.append(["에", "비스코"])
    input_cand.append(["의", "비스코"])
    code_dict, next_code = set_font(base_dir, font_table, src_font_canvas, start_code, 1, input_cand)
    ret_code_dict |= code_dict

    # set 4byte letters
    input_cand = []
    input_cand.append(["다이묘", font_name])
    input_cand.append(["와-과", font_name])
    input_cand.append(["은-는", font_name])
    input_cand.append(["을-를", font_name])
    input_cand.append(["이-가", font_name])

    input_cand.append(["도토미", font_name])
    input_cand.append(["무사시", "둥근모"])
    input_cand.append(["미카와", font_name])
    input_cand.append(["사가미", font_name])
    input_cand.append(["사누키", "둥근모"])
    input_cand.append(["사츠마", font_name])
    input_cand.append(["스루가", "둥근모"])
    input_cand.append(["시나노", "둥근모"])
    input_cand.append(["시모사", "둥근모"])
    input_cand.append(["야마토", "둥근모"])
    input_cand.append(["와카사", "둥근모"])
    input_cand.append(["에치고", font_name])
    input_cand.append(["에치젠", font_name])
    input_cand.append(["오와리", "둥근모"])
    input_cand.append(["이나바", "둥근모"])
    input_cand.append(["이마이", "둥근모"])
    input_cand.append(["이와미", "둥근모"])
    input_cand.append(["이즈모", font_name])
    input_cand.append(["코즈케", "둥근모"])
    input_cand.append(["키요스", "둥근모"])
    input_cand.append(["타지마", "둥근모"])
    input_cand.append(["하리마", font_name])
    input_cand.append(["히타치", font_name])

    code_dict, next_code = set_font(base_dir, font_table, src_font_canvas, next_code, 2, input_cand)
    ret_code_dict |= code_dict

    # Set merged 2byte letters
    letter_2byte = [[s, "default"] for s in letter_2byte]  # Change format
    code_dict, next_code = set_2byte_merge(base_dir, letter_2byte, font_table, src_font_canvas)
    print(f"Final code: {next_code}")
    ret_code_dict |= code_dict

    # Save font canvas image
    dst_font_canvas_path = base_dir / f"taikou2-{font_file}"
    pil_img = Image.fromarray(src_font_canvas)
    one_bit_img = pil_img.convert("1")
    one_bit_img.save(dst_font_canvas_path)
    with open(base_dir / "code.json", "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(ret_code_dict, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
