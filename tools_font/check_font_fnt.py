import cv2
import numpy as np
from pathlib import Path
from PIL import Image
from module.font_table import FontTable


def main():
    # font_tbl_path = Path("./font_table/font_table-kor-jin.json")
    font_tbl_path = Path("./font_table/font_table-jpn.json")
    font_fnt_path = Path("c:/work_han/font_/ThinDungGeunMo_cp949_full.fnt")

    font_table = FontTable(font_tbl_path)
    start_code = font_table.get_code("亜")  # 가
    code_list = list(font_table.code2char.keys())
    code_idx = code_list.index(start_code)
    code_list = code_list[code_idx:]

    # Pos of '亜' or '가' is 0xBE40   9F

    # idx = code_list.index(font_table.get_code("힝"))
    code = "989F"
    idx = code_list.index(code)
    if int(code, 16) < 0x9872:
        pass
    else:
        idx += 43

    with open(font_fnt_path, "rb") as f:
        data = bytearray(f.read())

    mem_pos = 0xBE40 + idx * 32

    # debug_draw(data, 0xBE40)
    width = 16
    img_1bpp = Image.frombytes("1", (width, 16), data[mem_pos : mem_pos + 32])
    img_8bpp = img_1bpp.convert("L")

    re_img_1bpp = img_8bpp.convert("1")
    re_data_1bpp = re_img_1bpp.tobytes()
    if data[mem_pos : mem_pos + 32] == re_data_1bpp:
        print("Match")

    scale_factor = 8
    new_width = width * scale_factor
    new_height = 16 * scale_factor
    resized_img = cv2.resize(np.array(img_8bpp), (new_width, new_height), interpolation=cv2.INTER_NEAREST)
    cv2.imshow("test", resized_img)
    cv2.waitKey()
    # img_8bpp.save("result.png")


if __name__ == "__main__":
    main()
