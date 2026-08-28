#!/usr/bin/env python3
"""Encode a localized CREDIT.DAT title PNG to its raw 1bpp replacement block."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


WIDTH = 384
HEIGHT = 48
STRIDE = WIDTH // 8
BLOCK_SIZE = STRIDE * HEIGHT


def encode_title(image: Image.Image) -> bytes:
    if image.size != (WIDTH, HEIGHT):
        raise ValueError(f"expected {WIDTH}x{HEIGHT}, got {image.width}x{image.height}")
    if image.mode != "P":
        raise ValueError(f"expected indexed P mode, got {image.mode}")

    pixels = list(image.getdata())
    used_indices = set(pixels)
    if not used_indices <= {0, 7}:
        unexpected = sorted(used_indices - {0, 7})
        raise ValueError(f"expected palette indices 0 and 7 only, got {unexpected}")

    encoded = bytearray()
    for y in range(HEIGHT):
        row = pixels[y * WIDTH : (y + 1) * WIDTH]
        for x in range(0, WIDTH, 8):
            value = 0
            for bit, index in enumerate(row[x : x + 8]):
                if index == 7:
                    value |= 0x80 >> bit
            encoded.append(value)

    if len(encoded) != BLOCK_SIZE:
        raise AssertionError("internal encoded-size mismatch")
    return bytes(encoded)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="384x48 indexed 000dd0.kor.png")
    parser.add_argument("output", type=Path, nargs="?", help="output 000dd0.kor.bin")
    args = parser.parse_args()

    output = args.output or args.input.with_suffix(".bin")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encode_title(Image.open(args.input)))
    print(f"{args.input} -> {output} ({BLOCK_SIZE:#x} bytes)")


if __name__ == "__main__":
    main()
