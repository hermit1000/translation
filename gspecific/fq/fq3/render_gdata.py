"""Render FQ3 GDATA.CHR's 8x16 glyph bank as a labeled PNG atlas."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .gdata_codec import decompress


GLYPH_BASE = 0x8400
GLYPH_COUNT = 256
COLUMNS = 16
SCALE = 3
CELL_WIDTH = 44
CELL_HEIGHT = 72


def render(source: Path, output: Path) -> None:
    decoded = decompress(source.read_bytes())
    if len(decoded) < GLYPH_BASE + GLYPH_COUNT * 16:
        raise ValueError(f"GDATA.CHR glyph bank is incomplete: {source}")
    atlas = Image.new("RGB", (COLUMNS * CELL_WIDTH, 16 * CELL_HEIGHT), "#202020")
    draw = ImageDraw.Draw(atlas)
    font = ImageFont.load_default()
    for slot in range(GLYPH_COUNT):
        left = (slot % COLUMNS) * CELL_WIDTH
        top = (slot // COLUMNS) * CELL_HEIGHT
        rows = decoded[GLYPH_BASE + slot * 16:GLYPH_BASE + (slot + 1) * 16]
        draw.rectangle((left, top, left + CELL_WIDTH - 2, top + CELL_HEIGHT - 2), outline="#666666")
        label = f"{slot:02X}"
        if 0x29 <= slot <= 0x62:
            label += f"/{slot + 0x7D:02X}"
        draw.text((left + 3, top + 2), label, fill="#ffdd77", font=font)
        for y, row in enumerate(rows):
            for x in range(8):
                if row & (0x80 >> x):
                    gx = left + 10 + x * SCALE
                    gy = top + 18 + y * SCALE
                    draw.rectangle((gx, gy, gx + SCALE - 1, gy + SCALE - 1), fill="white")
    output.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path,
                        default=Path(r"C:\work_han\workspace13"))
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    for directory, output in (("jpn-pc98", "GDATA.CHR_original.png"),
                              ("kor-pc98-dosbox-x", "GDATA.CHR_kor.png")):
        target = workspace / output
        render(workspace / directory / "GDATA.CHR", target)
        print(target)


if __name__ == "__main__":
    main()
