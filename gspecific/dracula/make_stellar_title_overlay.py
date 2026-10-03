#!/usr/bin/env python3
"""Create an arched, condensed Stellar Serif title overlay for TITLE2."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--mask-output", type=Path)
    parser.add_argument(
        "--font",
        type=Path,
        default=Path(r"C:\work_han\font_ext\Stellar_logo_AII\Stellar_Serif_Bold_Condensed.ttf"),
    )
    parser.add_argument("--solid", action="store_true", help="draw a single flat red color")
    args = parser.parse_args()

    canvas = Image.new("RGBA", (640, 400), (0, 0, 0, 0))
    mask = Image.new("L", canvas.size, 0)
    font = ImageFont.truetype(str(args.font), 108)
    text = "드라큘라 백작"
    advances = [font.getlength(char) for char in text]
    total_width = round(sum(advances))
    x0 = (640 - total_width) / 2
    top = 116

    # Keep the top edge nearly level, while shortening characters toward the
    # center so the lower edge forms the rounded arch of the source title.
    non_space = [i for i, char in enumerate(text) if char != " "]
    center = (non_space[0] + non_space[-1]) / 2
    radius = max(center - non_space[0], 1)
    x = x0
    for index, (char, advance) in enumerate(zip(text, advances)):
        if char == " ":
            x += advance
            continue
        glyph = Image.new("RGBA", (round(advance) + 18, 150), (0, 0, 0, 0))
        glyph_draw = ImageDraw.Draw(glyph)
        if args.solid:
            glyph_draw.text((9, -12), char, font=font, fill=(255, 0, 0, 255))
        else:
            glyph_draw.text((9, -8), char, font=font, fill=(34, 0, 0, 255),
                            stroke_width=5, stroke_fill=(0, 0, 0, 230))
            glyph_draw.text((9, -12), char, font=font, fill=(255, 0, 0, 255),
                            stroke_width=2, stroke_fill=(136, 0, 0, 255))
        glyph_mask = Image.new("L", glyph.size, 0)
        ImageDraw.Draw(glyph_mask).text((9, -12), char, font=font, fill=255,
                                        stroke_width=0, stroke_fill=255)

        distance = abs(index - center) / radius
        scale_y = 0.72 + 0.28 * min(distance, 1.0)
        new_height = round(glyph.height * scale_y)
        glyph = glyph.resize((glyph.width, new_height), Image.Resampling.LANCZOS)
        glyph_mask = glyph_mask.resize((glyph_mask.width, new_height), Image.Resampling.LANCZOS)
        canvas.alpha_composite(glyph, (round(x), top))
        mask.paste(glyph_mask, (round(x), top), glyph_mask)
        x += advance

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
