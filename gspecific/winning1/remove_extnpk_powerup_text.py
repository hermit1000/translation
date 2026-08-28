#!/usr/bin/env python3
"""Remove the lower Power-Up Kit text from EXTNPK 00af2b background."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


TEXT_BOX = (44, 343, 210, 384)
REFERENCE_X = 400
PATTERN_WIDTH = 8
ELLIPSE_BOX = (55, 300, 199, 345)
ELLIPSE_RESTORE_TOP = 343
BLUE = (0, 0, 255)


def remove_powerup_text(image: Image.Image) -> Image.Image:
    if image.size != (640, 400):
        raise ValueError(f"expected 640x400, got {image.width}x{image.height}")

    result = image.copy()
    source = image.load()
    target = result.load()
    left, top, right, bottom = TEXT_BOX

    # The clean background repeats every eight pixels horizontally. Copy the
    # matching phase from an unaffected area on the same row so horizontal
    # bands and dithering remain bit-exact.
    for y in range(top, bottom):
        for x in range(left, right):
            target[x, y] = source[REFERENCE_X + x % PATTERN_WIDTH, y]

    # The text overlaps the last three scanlines of the thin ellipse around
    # Winning Post. Restore only that missing lower arc; the surviving upper
    # ellipse and logo remain untouched.
    ellipse = Image.new("1", image.size, 0)
    ImageDraw.Draw(ellipse).ellipse(ELLIPSE_BOX, outline=1, width=1)
    ellipse_pixels = ellipse.load()
    for y in range(ELLIPSE_RESTORE_TOP, ELLIPSE_BOX[3] + 1):
        for x in range(ELLIPSE_BOX[0], ELLIPSE_BOX[2] + 1):
            if ellipse_pixels[x, y]:
                target[x, y] = BLUE
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    image = Image.open(args.input)
    result = remove_powerup_text(image)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.save(args.output)


if __name__ == "__main__":
    main()
