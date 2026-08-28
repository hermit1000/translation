#!/usr/bin/env python3
"""Render the localized BGSET title directly at its PC-98 bitmap size."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PC98_PALETTE = [
    (0, 0, 0),
    (0, 0, 255),
    (255, 0, 0),
    (255, 0, 255),
    (0, 255, 0),
    (0, 255, 255),
    (255, 255, 0),
    (255, 255, 255),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--text", default="경마 시뮬레이션 게임")
    parser.add_argument("--font-size", type=int, default=41)
    parser.add_argument("--threshold", type=int, default=128)
    args = parser.parse_args()

    font = ImageFont.truetype(str(args.font), args.font_size)
    scratch = Image.new("L", (512, 64), 0)
    ImageDraw.Draw(scratch).text((0, 0), args.text, font=font, fill=255, spacing=0)
    mask = scratch.point(lambda value: 7 if value >= args.threshold else 0)
    box = mask.getbbox()
    if box is None:
        raise ValueError("rendered text contains no foreground pixels")
    glyphs = mask.crop(box)

    canvas = Image.new("L", (384, 48), 0)
    x = (canvas.width - glyphs.width) // 2
    y = (canvas.height - glyphs.height) // 2
    canvas.paste(glyphs, (x, y))

    output = Image.new("P", canvas.size, 0)
    palette = [component for rgb in PC98_PALETTE for component in rgb]
    output.putpalette(palette + [0] * (768 - len(palette)))
    output.putdata(canvas.getdata())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.save(args.output)


if __name__ == "__main__":
    main()
