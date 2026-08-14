import cv2
import numpy as np
from pathlib import Path
from PIL import Image
from module.font_table import FontTable
from module.font_image import return_img_roi


def main():
    DEBUG = False

    font_name = "둥근모"  # "둥근모", "비스코"
    if font_name == "둥근모":
        font_file = "ThinDungGeunMo"
        ref_font_fnt_path = Path("../font_/ThinDungGeunMo_cp949_full.fnt")
    else:
        font_file = "BISCO"
        ref_font_fnt_path = Path("../font_dosjp/JIS_KOR.FNT")
    src_font_bmp_path = Path(f"../workspace2/taikou2-{font_file}.bmp")
    out_font_fnt_path = Path(f"../workspace2/taikou2-{font_file}.fnt")

    # font_tbl_path = Path("./font_table/font_table-kor-jin.json")
    font_tbl_path = Path("./font_table/font_table-jpn.json")

    code_start = "9540"
    code_end = "98AF"

    font_table = FontTable(font_tbl_path)

    # Pos of '亜' or '가' is 0xBE40
    base_code = font_table.get_code("亜")  # 가
    code_list = list(font_table.code2char.keys())
    code_idx = code_list.index(base_code)
    code_list = code_list[code_idx:]

    if DEBUG:
        # idx = code_list.index(font_table.get_code("힝"))
        code = "989F"
        idx = code_list.index(code)
        if int(code, 16) <= 0x9872:
            pass
        else:
            idx += 43

        with open(ref_font_fnt_path, "rb") as f:
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
    else:
        bmp = cv2.imread(src_font_bmp_path, 0)
        with open(ref_font_fnt_path, "rb") as f:
            fnt = bytearray(f.read())

        idx_start = code_list.index(code_start)
        idx_end = code_list.index(code_end)
        for idx in range(idx_start, idx_end + 1):
            code = code_list[idx]

            # Read font image from bmp
            roi = return_img_roi(code)
            crop = bmp[roi[0] : roi[1], roi[2] : roi[3]]
            crop = ~crop
            # crop_resized = cv2.resize(crop, dsize=(128, 128), interpolation=cv2.INTER_AREA)
            # cv2.imshow("patch_empty", crop_resized)
            # cv2.waitKey()
            img_8bpp = Image.fromarray(crop)
            data_1bpp = img_8bpp.convert("1").tobytes()

            # Get memory position of fnt
            if int(code, 16) <= 0x9872:
                fnt_idx = idx
            else:
                fnt_idx = idx + 43
            mem_pos = 0xBE40 + fnt_idx * 32

            # Input
            fnt[mem_pos : mem_pos + 32] = data_1bpp

        with open(out_font_fnt_path, "wb") as f:
            f.write(fnt)


if __name__ == "__main__":
    main()
