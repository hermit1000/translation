#!/usr/bin/env python3
"""Create a transparent Korean title overlay for TITLE2."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--mask-output", type=Path)
    parser.add_argument("--font", type=Path, default=Path(r"C:\Windows\Fonts\HANBatangB.ttf"))
    args = parser.parse_args()

    canvas = Image.new("RGBA", (640, 400), (0, 0, 0, 0))
    mask = Image.new("L", canvas.size, 0)
    draw = ImageDraw.Draw(canvas)
    mask_draw = ImageDraw.Draw(mask)
    font = ImageFont.truetype(str(args.font), 86)
    text = "드라큘라 백작"
    box = draw.textbbox((0, 0), text, font=font, stroke_width=0)
    text_width = box[2] - box[0]
    x = (640 - text_width) // 2
    y = 124

    # Dark shadow/edge, then the saturated red face used by TITLE2.
    draw.text((x + 3, y + 4), text, font=font, fill=(34, 0, 0, 255),
              stroke_width=4, stroke_fill=(0, 0, 0, 230))
    draw.text((x, y), text, font=font, fill=(255, 0, 0, 255),
              stroke_width=1, stroke_fill=(136, 0, 0, 255))
    mask_draw.text((x, y), text, font=font, fill=255, stroke_width=1, stroke_fill=255)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, format="PNG", optimize=True)
    if args.mask_output:
        args.mask_output.parent.mkdir(parents=True, exist_ok=True)
        mask.save(args.mask_output, format="PNG", optimize=True)
    print(f"wrote: {args.output}")
    if args.mask_output:
        print(f"wrote: {args.mask_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
