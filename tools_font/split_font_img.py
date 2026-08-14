import cv2
from PIL import Image
from pathlib import Path
from module.font_image import imread_korean


def crop_paste(img_src, img_dst, roi_src, roi_dst):
    img_dst[roi_dst[0] : roi_dst[1], roi_dst[2] : roi_dst[3]] = img_src[
        roi_src[0] : roi_src[1], roi_src[2] : roi_src[3]
    ]
    return img_dst


def main():
    font_img_path = "C:/work_han/font_update_db/안개폭풍.bmp"
    out_img_folder = Path("C:/work_han/font_update_db/test")
    img_src = imread_korean(font_img_path)

    invert = True
    width_cut = 8

    h, w = img_src.shape
    print(h, w)
    count = h // 16
    print(count)

    for i in range(count):
        img_dst = img_src[i * 16 : (i + 1) * 16, :]

        if invert:
            img_dst = cv2.bitwise_not(img_dst)

        if width_cut != 0:
            wcnt = w // width_cut
            for j in range(wcnt):
                img_cut = img_dst[:, j * width_cut : (j + 1) * width_cut]
                img_pil = Image.fromarray(img_cut).convert("1")
                save_path = out_img_folder / f"{i}_{j}.bmp"
                img_pil.save(save_path)

        else:
            img_pil = Image.fromarray(img_dst).convert("1")
            save_path = out_img_folder / f"{i}.bmp"
            img_pil.save(save_path)


if __name__ == "__main__":
    main()
