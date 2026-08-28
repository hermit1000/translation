#!/usr/bin/env python3
"""Convert a generated Korean BGSET title to the game's indexed 1bpp PNG."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


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
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, default=384)
    parser.add_argument("--height", type=int, default=48)
    parser.add_argument("--ink-height", type=int, default=37)
    parser.add_argument("--threshold", type=int, default=64)
    args = parser.parse_args()

    gray = Image.open(args.input).convert("L")
    mask = gray.point(lambda value: 255 if value > args.threshold else 0)
    box = mask.getbbox()
    if box is None:
        raise ValueError("input contains no foreground pixels")

    glyphs = mask.crop(box)
    target_width = round(glyphs.width * args.ink_height / glyphs.height)
    if target_width > args.width:
        target_width = args.width
    glyphs = glyphs.resize((target_width, args.ink_height), Image.Resampling.NEAREST)

    indices = Image.new("P", (args.width, args.height), 0)
    palette = [component for rgb in PC98_PALETTE for component in rgb]
    indices.putpalette(palette + [0] * (768 - len(palette)))
    foreground = glyphs.point(lambda value: 7 if value else 0)
    x = (args.width - target_width) // 2
    y = (args.height - args.ink_height) // 2
    indices.paste(foreground, (x, y))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    indices.save(args.output)


if __name__ == "__main__":
    main()
