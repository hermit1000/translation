#!/usr/bin/env python3
"""Make a narrower title overlay with a stronger semicircular lower edge."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def make_arch(source: Path, output: Path) -> None:
    image = Image.open(source).convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError(f"overlay is empty: {source}")
    cropped = image.crop(bbox).resize((512, 145), Image.Resampling.LANCZOS)
    pixels = np.asarray(cropped)
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    top = 113
    left = 64
    # Preserve a level top while making the center substantially shorter.
    for x in range(pixels.shape[1]):
        edge_distance = abs((x / (pixels.shape[1] - 1)) * 2.0 - 1.0)
        factor = 0.66 + 0.34 * (edge_distance ** 1.15)
        column = Image.fromarray(pixels[:, x:x + 1], mode="RGBA")
        height = max(1, round(pixels.shape[0] * factor))
        column = column.resize((1, height), Image.Resampling.LANCZOS)
        result.alpha_composite(column, (left + x, top))
    # Remove interpolation halos: this is a flat-color PC-98 overlay, so its
    # edge must be either fully present or fully transparent.
    alpha = result.getchannel("A").point(lambda value: 255 if value >= 160 else 0)
    solid = Image.new("RGBA", result.size, (0, 0, 0, 0))
    solid.paste((255, 0, 0, 255), mask=alpha)
    result = solid
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output, format="PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    make_arch(args.source, args.output)
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
