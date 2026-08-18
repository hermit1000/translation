import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from module.font_table import FontTable
from module.font_image import return_img_roi, return_img_roi_1byte


def crop_paste(img_src, img_dst, roi_src, roi_dst):
    img_dst[roi_dst[0] : roi_dst[1], roi_dst[2] : roi_dst[3]] = img_src[
        roi_src[0] : roi_src[1], roi_src[2] : roi_src[3]
    ]
    return img_dst


def get_glyphs(script, font_table):
    """Return (code, width, roi) tuples; ``|`` marks the next char as 1-byte."""
    glyphs = []
    half_width = False

    for character in script:
        if character == "|":
            if half_width:
                raise ValueError("A half-width marker cannot follow another marker.")
            half_width = True
            continue

        if half_width:
            code = font_table.get_code_ascii(character)
            width = 8
        else:
            code = font_table.get_code(character)
            width = 16

        resize_half = False
        if half_width and code is None:
            # ASCII punctuation is also present as a 2-byte glyph in the
            # image table; use it as the source when no dedicated 1-byte
            # glyph exists.
            code = font_table.get_code(character)
            resize_half = True

        if code is None:
            kind = "half-width" if half_width else "full-width"
            raise ValueError(f"No {kind} font code for {character!r}.")

        if half_width:
            if resize_half:
                roi = return_img_roi(code)
            else:
                roi = return_img_roi_1byte(code)
        else:
            roi = return_img_roi(code)

        glyphs.append((code, width, roi, resize_half))
        half_width = False

    if half_width:
        raise ValueError("The script ends with a half-width marker ('|').")

    return glyphs


def main():
    font_out_dir = "c:/work_han/font_update_db/test"

    font_name = "비스코"  # "둥근모", "비스코"
    if font_name == "둥근모":
        font_bmp_path = "c:/work_han/ThinDungGeunMo.bmp"
    if font_name == "비스코":
        font_bmp_path = "c:/work_han/BISCO.bmp"

    img_src = cv2.imread(font_bmp_path, 0)

    script = "|(이|)라"
    font_table_kor = FontTable(Path("font_table/font_table-kor-jin.json"))
    glyphs = get_glyphs(script, font_table_kor)

    canvas = np.zeros((16, sum(width for _, width, _, _ in glyphs)), dtype=np.uint8)
    x = 0
    for _, width, roi, resize_half in glyphs:
        # ypos = 33 * 16
        # xpos = 2 * 16
        # crop = img_src[ypos : ypos + 16, xpos : xpos + 16]

        glyph = img_src[roi[0] : roi[1], roi[2] : roi[3]]
        if resize_half:
            glyph = cv2.resize(glyph, (width, 16), interpolation=cv2.INTER_AREA)
        canvas[:, x : x + width] = glyph
        x += width

    img_pil = Image.fromarray(canvas).convert("1")
    img_pil.save(f"{font_out_dir}/{script.replace('|', '')}.bmp")
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
