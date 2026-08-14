import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from module.font_table import FontTable
from module.font_image import return_img_roi


def crop_paste(img_src, img_dst, roi_src, roi_dst):
    img_dst[roi_dst[0] : roi_dst[1], roi_dst[2] : roi_dst[3]] = img_src[
        roi_src[0] : roi_src[1], roi_src[2] : roi_src[3]
    ]
    return img_dst


def main():
    font_out_dir = "c:/work_han/font_update_db/test"

    font_name = "둥근모"  # "둥근모", "비스코"
    if font_name == "둥근모":
        font_bmp_path = "c:/work_han/ThinDungGeunMo.bmp"
    if font_name == "비스코":
        font_bmp_path = "c:/work_han/BISCO.bmp"

    img_src = cv2.imread(font_bmp_path, 0)

    script = "히에이산"
    font_table_kor = FontTable(Path("font_table/font_table-kor-jin.json"))
    codes = font_table_kor.get_codes(script)

    code = ""
    for code_hex in codes:
        code += code_hex

    # val = 0x889F
    # code = ""
    # for i in range(4):
    #     code += f"{val:X}"
    #     val += 1

    # code = "935791968CB4"
    # code = code.replace("0x:", "")
    # code = code.split("#")[0]

    if len(code) % 2 != 0:
        assert 0, f"The length of code is not matched. {code}"

    num_chars = len(code) // 4
    canvas = np.zeros((16, num_chars * 16), dtype=np.uint8)
    for i in range(num_chars):
        roi = return_img_roi(code[i * 4 : (i + 1) * 4])
        # ypos = 33 * 16
        # xpos = 2 * 16
        # crop = img_src[ypos : ypos + 16, xpos : xpos + 16]

        canvas[:, 16 * i : 16 * (i + 1)] = img_src[roi[0] : roi[1], roi[2] : roi[3]]

    img_pil = Image.fromarray(canvas).convert("1")
    img_pil.save(f"{font_out_dir}/{script}.bmp")
    return

    h, w = canvas.shape
    nh = h * 8
    nw = w * 8
    resized = cv2.resize(canvas, dsize=(nw, nh), interpolation=cv2.INTER_AREA)
    cv2.imshow("patch", resized)
    cv2.waitKey()
    cv2.imwrite("debug.png", canvas)


if __name__ == "__main__":
    main()
