import cv2
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
    DEBUG = False
    src_font_bmp_path = Path("c:/work_han/font2/inindo-font-kor.bmp")
    dst_font_bmp_path = Path("c:/work_han/font2/BISCO.bmp")

    # Read font table
    src_font_table_path = Path("font_table/font_table-kor-jin.json")
    src_table = FontTable(src_font_table_path)

    mod_font_table_path = Path("font_table/font_table-kor-convert.json")
    mod_table = FontTable(mod_font_table_path)

    img_src = cv2.imread(src_font_bmp_path, 0)
    img_dst = cv2.imread(dst_font_bmp_path, 0)
    # img_dst = img_src.copy()

    if DEBUG:
        val_after = src_table.get_code("괌")
        val = src_table.get_code("가")
        print(val, val_after)
        roi = return_img_roi(val, DEBUG)
        # ypos = 33 * 16
        # xpos = 2 * 16
        # crop = img_src[ypos : ypos + 16, xpos : xpos + 16]
        crop = img_src[roi[0] : roi[1], roi[2] : roi[3]]
        crop_resized = cv2.resize(crop, dsize=(128, 128), interpolation=cv2.INTER_AREA)
        cv2.imshow("patch_empty", crop_resized)
        cv2.waitKey(1000)
        return
    else:
        for dst_code, src_char in mod_table.code2char.items():
            src_code = src_table.get_code(src_char)
            src_roi = return_img_roi(src_code)
            dst_roi = return_img_roi(dst_code)
            # if src_roi == dst_roi:
            #     continue
            # print(src_char)
            img_dst = crop_paste(img_src, img_dst, src_roi, dst_roi)

    # Thresholding
    img_pil = Image.fromarray(img_dst).convert("1")
    img_pil.save(dst_font_bmp_path)


if __name__ == "__main__":
    main()
