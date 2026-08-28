#!/usr/bin/env python3
"""Render Korean Power-Up Kit text over the cleaned EXTNPK 00af2b background."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


TEXT = "파워업키트"
BLUE = (0, 0, 255)
BLACK = (0, 0, 0)
SHADOW_OFFSET = (1, 1)
FONT_SIZE = 32
TEXT_TOP_INSET = 4
TEXT_X_OFFSET = 0
TEXT_Y_OFFSET = 0
BAR_HEIGHT = 3
BAR_SHADOW_HEIGHT = 1
BAR_Y_OFFSET = 0
JAPANESE_TEXT_REGION = (50, 343, 209, 384)
DEFAULT_DIRECTORY = Path(r"C:\work_han\workspace3\binary_inputs-pc98\EXTNPK.NPK")
DEFAULT_BACKGROUND = DEFAULT_DIRECTORY / "00af2b.bg.png"
DEFAULT_JAPANESE = DEFAULT_DIRECTORY / "00af2b.jpn.png"
DEFAULT_OUTPUT = DEFAULT_DIRECTORY / "00af2b.kor.png"
DEFAULT_FONT = Path(r"C:\work_han\font_ext\ext\나눔\NanumGothicExtraBold.ttf")


def render_mask(font_path: Path) -> Image.Image:
    font = ImageFont.truetype(str(font_path), FONT_SIZE)
    scratch = Image.new("L", (512, 96), 0)
    ImageDraw.Draw(scratch).text((0, 0), TEXT, font=font, fill=255)
    box = scratch.getbbox()
    if box is None:
        raise ValueError("font rendered no foreground pixels")
    return scratch.crop(box).point(lambda value: 255 if value >= 128 else 0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "background",
        type=Path,
        nargs="?",
        default=DEFAULT_BACKGROUND,
        help=f"clean background (default: {DEFAULT_BACKGROUND})",
    )
    parser.add_argument(
        "japanese",
        type=Path,
        nargs="?",
        default=DEFAULT_JAPANESE,
        help=f"original Japanese image (default: {DEFAULT_JAPANESE})",
    )
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=DEFAULT_OUTPUT,
        help=f"Korean output (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--text-x-offset", type=int, default=TEXT_X_OFFSET)
    parser.add_argument("--text-y-offset", type=int, default=TEXT_Y_OFFSET)
    parser.add_argument("--bar-y-offset", type=int, default=BAR_Y_OFFSET)
    args = parser.parse_args()

    background = Image.open(args.background).convert("RGB")
    japanese = Image.open(args.japanese).convert("RGB")
    if background.size != japanese.size:
        raise ValueError("background and Japanese images must have the same size")

    raw_diff_box = ImageChops.difference(background, japanese).getbbox()
    if raw_diff_box is None:
        raise ValueError("background and Japanese images are identical")
    text_box = (
        max(raw_diff_box[0], JAPANESE_TEXT_REGION[0]),
        max(raw_diff_box[1], JAPANESE_TEXT_REGION[1]),
        min(raw_diff_box[2], JAPANESE_TEXT_REGION[2]),
        min(raw_diff_box[3], JAPANESE_TEXT_REGION[3]),
    )
    left, top, right, bottom = text_box
    shadow_x, shadow_y = SHADOW_OFFSET
    mask = render_mask(args.font)
    glyph_width, glyph_height = mask.size
    available_width = right - left
    if glyph_width + shadow_x > available_width:
        raise ValueError(f"rendered text is too wide for {text_box}: {mask.size}")

    result = background.copy()
    shadow = Image.new("RGB", mask.size, BLACK)
    fill = Image.new("RGB", mask.size, BLUE)
    text_x = left + (available_width - glyph_width) // 2 + args.text_x_offset
    text_y = top + TEXT_TOP_INSET + args.text_y_offset
    result.paste(shadow, (text_x + shadow_x, text_y + shadow_y), mask)
    result.paste(fill, (text_x, text_y), mask)

    bar_top = bottom - BAR_HEIGHT - BAR_SHADOW_HEIGHT + args.bar_y_offset
    ImageDraw.Draw(result).rectangle(
        (
            left + shadow_x,
            bar_top + BAR_HEIGHT,
            right - 1,
            bar_top + BAR_HEIGHT + BAR_SHADOW_HEIGHT - 1,
        ),
        fill=BLACK,
    )
    ImageDraw.Draw(result).rectangle((left, bar_top, right - 1 - shadow_x, bar_top + BAR_HEIGHT - 1), fill=BLUE)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.save(args.output)
    print(
        f"text bbox {text_box}, glyph {glyph_width}x{glyph_height} at "
        f"({text_x},{text_y}), bar y={bar_top}:{bottom}, shadow {SHADOW_OFFSET}"
    )


if __name__ == "__main__":
    main()
