import json
import numpy as np
from PIL import Image
from pathlib import Path
from module.font_image import imread_korean, return_img_roi


def main():
    platform = "dos"
    platform = "pc98"

    ws_num = 0

    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_base_dir = base_dir / f"script-{platform}"
    font_image_path = base_dir / "inindo-font-kor.bmp"
    save_base_dir = base_dir / "image"

    # ===================================================================

    font_image = imread_korean(str(font_image_path))

    custom_word_path = script_base_dir / "custom_word.json"
    custom_words = {}
    if custom_word_path.exists():
        with open(custom_word_path, "r", encoding="utf-8") as f:
            custom_words = json.load(f)

    for name, code in custom_words.items():
        print(name)
        if len(code) % 2 != 0:
            assert 0, f"The length of code is not matched. {code}"

        num_chars = len(code) // 4
        print(num_chars)
        canvas = np.zeros((16, num_chars * 16), dtype=np.uint8)
        for i in range(num_chars):
            if code[i * 4 : (i + 1) * 4] == "0000":
                canvas = canvas[:, : 16 * i]
            else:
                roi = return_img_roi(code[i * 4 : (i + 1) * 4])
                canvas[:, 16 * i : 16 * (i + 1)] = font_image[roi[0] : roi[1], roi[2] : roi[3]]

        pil_img = Image.fromarray(canvas)
        one_bit_img = pil_img.convert("1")
        one_bit_img.save(str(save_base_dir / f"{name}.bmp"))


if __name__ == "__main__":
    main()
