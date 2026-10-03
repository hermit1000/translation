#!/usr/bin/env python3
"""Stretch a title overlay into the wide oval proportions of TITLE2."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def stretch(source: Path, output: Path, box: tuple[int, int, int, int]) -> None:
    image = Image.open(source).convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError(f"overlay is empty: {source}")
    cropped = image.crop(bbox)
    width = box[2] - box[0]
    height = box[3] - box[1]
    resized = cropped.resize((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", image.size, (0, 0, 0, 0))
    canvas.alpha_composite(resized, (box[0], box[1]))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mask-source", type=Path)
    parser.add_argument("--mask-output", type=Path)
    args = parser.parse_args()

    # Approximate the original ドラキュラ伯爵 title bounds in TITLE2.
    title_box = (52, 113, 590, 258)
    stretch(args.source, args.output, title_box)
    if args.mask_source and args.mask_output:
        stretch(args.mask_source, args.mask_output, title_box)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
