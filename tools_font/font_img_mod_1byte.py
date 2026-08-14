import cv2
from PIL import Image
from pathlib import Path
from module.font_image import imread_korean, return_img_roi_1byte


def main():
    DEBUG = False
    src_font_bmp_path = "c:/work_han/workspace4/nobu4-BISCO.bmp"
    sav_font_bmp_path = "c:/work_han/workspace4/nobu4-BISCO-mod.bmp"

    img_mod = cv2.imread(src_font_bmp_path, 0)

    if DEBUG:
        val = "0xC1"
        print(val)
        roi = return_img_roi_1byte(val, DEBUG)
        crop = img_mod[roi[0] : roi[1], roi[2] : roi[3]]

        img_pil = Image.fromarray(crop).convert("1")
        img_pil.save("c:/work_han/test.bmp")

        crop_resized = cv2.resize(crop, dsize=(64, 128), interpolation=cv2.INTER_AREA)
        cv2.imshow("patch_empty", crop_resized)
        cv2.waitKey()
        return
    else:
        font_dir = Path("C:/work_han/font_update_db/byte1")
        target_list = ["니", "로", "베", "에", "요", "유", "이", "조", "쥰", "츠", "켄", "혼", "히"]
        target_list.sort()
        print(target_list)

        start_code_int = 0xB1

        for i, letter in enumerate(target_list):
            roi = return_img_roi_1byte(hex(start_code_int + i))
            font_path = font_dir / f"{letter}.bmp"
            if not font_path.exists():
                print(f"{font_path} does not exist.")
                continue
            kor_font = imread_korean(font_path)
            img_mod[roi[0] : roi[1], roi[2] : roi[3]] = kor_font

        # Thresholding
        img_pil = Image.fromarray(img_mod).convert("1")
        img_pil.save(sav_font_bmp_path)


if __name__ == "__main__":
    main()
