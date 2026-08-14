import numpy as np
import cv2


def debug_draw(
    data,
    offset,
    font_height=16,
    font_width=16,
):
    # Initialize the buffer with 255 (white)
    canvas_gray = np.full((font_height, font_width), 255, dtype=np.uint8)

    target_data = data[offset : offset + 32]

    if font_width not in (8, 16):
        raise ValueError(f"font_width should be 8 or 16, but {font_width} is given.")

    bit_index = 0
    for y in range(font_height):
        for x in range(font_width):
            byte_val = target_data[bit_index // 8]
            bit_in_byte = 7 - (bit_index % 8)  # Assuming reading from MSB
            pixel_value_1bit = (byte_val >> bit_in_byte) & 1

            # Map 1-bit value to 0 (black) or 255 (white)
            canvas_gray[y, x] = 255 if pixel_value_1bit == 1 else 0
            bit_index += 1

    scale_factor = 8
    new_width = font_width * scale_factor
    new_height = font_height * scale_factor
    resized_img = cv2.resize(canvas_gray, (new_width, new_height), interpolation=cv2.INTER_NEAREST)
    # resized_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_LINEAR)

    cv2.imshow("test", resized_img)
    cv2.waitKey()


def main():
    font_jpn_path = "C:/work_han/font_dosjp/JIS.FNT"
    font_gen_path = "C:/work_han/font_dosjp/JIS_genpei.FNT"
    font_kor_path = "C:/work_han/font_dosjp/JIS_KOR.FNT"

    # Read jpn font data
    with open(font_jpn_path, "rb") as f:
        font_jpn_data = f.read()
    font_jpn_data = bytearray(font_jpn_data)

    with open(font_gen_path, "rb") as f:
        font_gen_data = f.read()
    font_gen_data = bytearray(font_gen_data)

    # 2-byte font 1 pixel-width.
    # For 16x16, 1 letter is 2x16 = 32 bytes.
    # 32 bytes is the basic offset for a letter.
    print(len(font_jpn_data))
    offset_start = (16 * 95 + 2) * 32  # "889F": "亜", "가"
    offset_end = (16 * 241 + 15) * 32  # "94FC": "美", "힝"
    offset_end += 32

    # debug_draw(font_gen_data, offset, 16, 16)

    font_jpn_data[offset_start:offset_end] = font_gen_data[offset_start:offset_end]

    with open(font_kor_path, "wb") as f:
        f.write(font_jpn_data)


if __name__ == "__main__":
    main()
