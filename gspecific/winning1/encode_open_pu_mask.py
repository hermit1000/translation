#!/usr/bin/env python3
"""Rebuild the OPEN_PU.DAT 007435 1bpp mask for a localized PNG."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


WIDTH = 368
HEIGHT = 200


def rgb(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        raise ValueError(f"{path}: expected {WIDTH}x{HEIGHT}, got {image.size}")
    return image


def rebuild_mask(
    original_mask_path: Path,
    original_image_path: Path,
    background_path: Path,
    localized_image_path: Path,
) -> Image.Image:
    original_mask = Image.open(original_mask_path).convert("L")
    if original_mask.size != (WIDTH, HEIGHT):
        raise ValueError(f"unexpected mask size: {original_mask.size}")
    original = rgb(original_image_path)
    background = rgb(background_path)
    localized = rgb(localized_image_path)

    result = original_mask.point(lambda value: 255 if value >= 128 else 0)
    mask_pixels = result.load()
    original_pixels = original.load()
    background_pixels = background.load()
    localized_pixels = localized.load()

    for y in range(HEIGHT):
        for x in range(WIDTH):
            # Remove only pixels belonging to artwork erased from the Japanese
            # source. Preserve all special logo-mask pixels outside that area.
            if original_pixels[x, y] != background_pixels[x, y]:
                mask_pixels[x, y] = (
                    0 if background_pixels[x, y] != (0, 0, 0) else 255
                )
            # Add every localized glyph/bar pixel introduced over the clean bg.
            if localized_pixels[x, y] != background_pixels[x, y]:
                mask_pixels[x, y] = 0
    return result


def encode_msb_first(mask: Image.Image) -> bytes:
    pixels = mask.load()
    output = bytearray()
    for y in range(HEIGHT):
        for x in range(0, WIDTH, 8):
            value = 0
            for bit in range(8):
                if pixels[x + bit, y] >= 128:
                    value |= 1 << (7 - bit)
            output.append(value)
    expected = WIDTH * HEIGHT // 8
    if len(output) != expected:
        raise AssertionError(f"expected {expected} bytes, got {len(output)}")
    return bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_mask", type=Path)
    parser.add_argument("original_image", type=Path)
    parser.add_argument("background", type=Path)
    parser.add_argument("localized_image", type=Path)
    parser.add_argument("output_png", type=Path)
    parser.add_argument("output_bin", type=Path)
    args = parser.parse_args()

    mask = rebuild_mask(
        args.original_mask,
        args.original_image,
        args.background,
        args.localized_image,
    )
    args.output_png.parent.mkdir(parents=True, exist_ok=True)
    args.output_bin.parent.mkdir(parents=True, exist_ok=True)
    mask.convert("RGB").save(args.output_png)
    encoded = encode_msb_first(mask)
    args.output_bin.write_bytes(encoded)

    # Verify the exact bitstream by decoding it again.
    decoded = bytes(
        255 if byte & (1 << bit) else 0
        for byte in encoded
        for bit in range(7, -1, -1)
    )
    if decoded != mask.tobytes():
        raise AssertionError("mask round-trip verification failed")
    print(f"{args.output_png}, {args.output_bin} ({len(encoded)} bytes)")


if __name__ == "__main__":
    main()
