import json
import numpy as np
from PIL import Image
from pathlib import Path
from module.name_db import NameDB
from module.font_image import imread_korean


def draw_and_save(font_dir: Path, save_dir: Path, name: str):
    name = name.replace(" ", "_")
    if not len(name):
        return

    if len(name) == 1:
        print(1)

    height = 16
    width = len(name) * 8

    canvas = np.zeros((height, width), dtype=np.uint8)

    for i, letter in enumerate(name):
        letter_path = font_dir / f"{letter}.bmp"
        img = imread_korean(str(letter_path))
        canvas[0 : img.shape[0], i * 8 : i * 8 + img.shape[1]] = img

    pil_img = Image.fromarray(canvas)
    one_bit_img = pil_img.convert("1")
    one_bit_img.save(save_dir / f"{name}.bmp")


def main():
    base_dir = Path("c:/work_han/font_update_db")
    db_dir = Path("C:/work_han/translation/name_db")
    save_dir = Path("c:/work_han/font_update_db/test")

    # Name
    db = NameDB()
    for _, korean_name, _ in db.iter_name_pairs("nb4"):
        draw_and_save(base_dir / "byte1", save_dir, str(korean_name))

    # Region
    with open(db_dir / "region_db.json", "r", encoding="utf-8") as f:
        region_db = json.load(f)
        for v in region_db.values():
            draw_and_save(base_dir / "byte1", save_dir, v)

    # Mountain, etc.
    with open(db_dir / "nb4" / "nb4_산천성.json", "r", encoding="utf-8") as f:
        san_db = json.load(f)
        for v in san_db.values():
            text = v["kor"]
            if text[-1] == "산":
                text = text[:-1]
            if text[-2:] == "산성":
                text = text[:-2]
            draw_and_save(base_dir / "byte1", save_dir, text)

    # 다기
    with open(db_dir / "nb4" / "nb4_다기.json", "r", encoding="utf-8") as f:
        san_db = json.load(f)

        for v in san_db.values():
            kor = v["kor"]
            draw_and_save(base_dir / "byte1", save_dir, kor)


if __name__ == "__main__":
    main()
