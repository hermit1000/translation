import cv2
import json
from PIL import Image
from pathlib import Path
from module.name_db import NameDB
from module.font_table import FontTable
from module.font_image import add_text_pairs, set_2byte_merge, set_font


TARGET_GAME = "nb3"


def has_game(entry: dict, game: str) -> bool:
    games = entry.get("game", [])
    if isinstance(games, str):
        games = [games]
    return game in games


def iter_region_texts(region_db: dict, game: str):
    for entry in region_db.values():
        if isinstance(entry, str):
            yield entry
            continue

        if has_game(entry, game):
            yield entry["kor"]


def iter_nb3_region_texts(region_db: dict):
    yield from iter_region_texts(region_db, TARGET_GAME)


def main():
    base_dir = Path("c:/work_han/font_update_db")
    db_dir = Path("C:/work_han/translation/name_db")

    font_table = FontTable(Path("font_table/font_table-jpn.json"))
    src_font_canvas_path = base_dir / "BISCO.bmp"
    src_font_canvas = cv2.imread(str(src_font_canvas_path), cv2.IMREAD_GRAYSCALE)

    letter_2byte = set()
    # Add custom word
    letter_2byte.add("여름")
    letter_2byte.add("가을")
    letter_2byte.add("겨울")
    letter_2byte.add("아침")

    # Name
    db = NameDB()
    for _, korean_name, _ in db.iter_name_pairs("nb3"):
        for kor in (korean_name.family, korean_name.given):
            space = add_text_pairs(kor, letter_2byte)
            if space:
                print(1)

    # Region
    with open(db_dir / "region_db.json", "r", encoding="utf-8") as f:
        region_db = json.load(f)
        for text in iter_nb3_region_texts(region_db):
            space = add_text_pairs(text, letter_2byte)
            if space:
                print(1)

    letter_2byte = list(letter_2byte)
    letter_2byte.sort()
    print(len(letter_2byte))
    # print(letter_2byte)

    ret_code_dict = {}

    # set 4byte letters
    input_cand_4byte = []
    input_cand_4byte.append(["다이묘", "비스코"])
    input_cand_4byte.append(["와-과", "비스코"])
    input_cand_4byte.append(["은-는", "비스코"])
    input_cand_4byte.append(["을-를", "비스코"])
    input_cand_4byte.append(["이-가", "비스코"])

    code_dict, _ = set_font(
        base_dir,
        font_table,
        src_font_canvas,
        "9540",  # 鼻
        2,
        input_cand_4byte,
    )
    ret_code_dict |= code_dict

    # Set 2byte letters
    letter_2byte = [[s, "default"] for s in letter_2byte]  # Change format
    code_dict, _ = set_2byte_merge(base_dir, letter_2byte, font_table, src_font_canvas)
    ret_code_dict |= code_dict

    # Save font canvas image
    dst_font_canvas_path = base_dir / "nobu3-BISCO.bmp"
    pil_img = Image.fromarray(src_font_canvas)
    one_bit_img = pil_img.convert("1")
    one_bit_img.save(dst_font_canvas_path)
    with open(base_dir / "code.json", "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(ret_code_dict, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
