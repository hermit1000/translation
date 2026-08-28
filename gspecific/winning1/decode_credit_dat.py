#!/usr/bin/env python3
"""Decode the Winning Post title bitmap stored in CREDIT.DAT."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


OFFSET = 0x0DD0
WIDTH = 384
HEIGHT = 48
STRIDE = WIDTH // 8
BLOCK_SIZE = STRIDE * HEIGHT
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


def decode_title(data: bytes) -> Image.Image:
    if len(data) != BLOCK_SIZE:
        raise ValueError(f"expected {BLOCK_SIZE:#x} bytes, got {len(data):#x}")

    pixels = bytearray()
    for value in data:
        pixels.extend(7 if value & (0x80 >> bit) else 0 for bit in range(8))

    image = Image.frombytes("P", (WIDTH, HEIGHT), bytes(pixels))
    palette = [component for rgb in PC98_PALETTE for component in rgb]
    image.putpalette(palette + [0] * (768 - len(palette)))
    return image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="original CREDIT.DAT")
    parser.add_argument("output", type=Path, help="output 000dd0.jpn.png")
    parser.add_argument("--offset", type=lambda value: int(value, 0), default=OFFSET)
    args = parser.parse_args()

    source = args.input.read_bytes()
    end = args.offset + BLOCK_SIZE
    if end > len(source):
        raise ValueError(
            f"CREDIT.DAT is too short for {args.offset:#x}..{end - 1:#x}: {len(source):#x}"
        )
    block = source[args.offset:end]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    decode_title(block).save(args.output)
    metadata = {
        "source": args.input.as_posix(),
        "file_offset": f"0x{args.offset:06X}",
        "original_size": BLOCK_SIZE,
        "compression": "none",
        "width": WIDTH,
        "height": HEIGHT,
        "stride": STRIDE,
        "bits_per_pixel": 1,
        "bit_order": "msb-first",
        "foreground_palette_index": 7,
        "palette": "PC-98 digital 8-color",
    }
    args.output.with_suffix(".meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{args.input}[{args.offset:#x}:{end:#x}] -> {args.output}")


if __name__ == "__main__":
    main()
