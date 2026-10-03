#!/usr/bin/env python3
"""Remove TITLE2 text while preserving its indexed PC-98 palette."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def make_mask(indices: np.ndarray) -> np.ndarray:
    mask = np.zeros(indices.shape, dtype=np.uint8)

    # Main red title: start from the saturated glyph colors and grow the mask
    # over their anti-aliased edges, without erasing the whole brick panel.
    main = np.zeros_like(mask)
    main[115:270, 55:590] = 1
    mask[(main == 1) & np.isin(indices, (11, 12, 13))] = 255

    # Japanese subtitle and the lower-right colour-work label.
    subtitle = np.zeros_like(mask)
    subtitle[86:120, 205:435] = 1
    lower_label = np.zeros_like(mask)
    lower_label[288:330, 410:560] = 1
    light_text = np.isin(indices, (6, 7, 14))
    mask[((subtitle == 1) | (lower_label == 1)) & light_text] = 255

    mask = cv2.dilate(mask, np.ones((3, 3), dtype=np.uint8), iterations=1)
    return mask


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    source = Image.open(args.source).convert("P")
    if source.size != (640, 400):
        raise ValueError(f"TITLE2 must be 640x400, got {source.size}")
    palette = source.getpalette()[: 16 * 3]
    indices = np.asarray(source, dtype=np.uint8)
    mask = make_mask(indices)

    rgb = np.asarray(source.convert("RGB"), dtype=np.uint8)
    repaired = cv2.inpaint(rgb, mask, 3, cv2.INPAINT_TELEA)

    # Use int32: squaring an int16 RGB difference can overflow at 255**2.
    palette_rgb = np.asarray(palette, dtype=np.int32).reshape((-1, 3))
    distance = ((repaired[:, :, None, :].astype(np.int32) - palette_rgb[None, None, :, :]) ** 2).sum(axis=3)
    repaired_indices = distance.argmin(axis=2).astype(np.uint8)

    # Keep the original gray mortar pixels exactly; they are structural
    # borders between bricks and should not be altered by inpainting.
    mortar = np.isin(indices, (8, 9, 10))
    repaired_indices[mortar] = indices[mortar]

    output = Image.fromarray(repaired_indices, mode="P")
    full_palette = source.getpalette()
    output.putpalette(full_palette)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.save(args.output, format="PNG", optimize=True)
    print(f"wrote: {args.output} (masked_pixels={int((mask > 0).sum())})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
