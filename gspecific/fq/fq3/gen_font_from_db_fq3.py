"""Build FQ3's font from the BISCO atlas and FQ3 glyph database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops

from module.font_image import return_img_roi


WORKSPACE = Path(r"C:\work_han\workspace13")
FONT_DB = Path(r"C:\work_han\font_update_db")


def build_font(workspace: Path, font_db: Path) -> Image.Image:
    words = json.loads((workspace / "script-pc98" / "custom_word.json").read_text(encoding="utf-8"))
    halfwidth = {int(code, 16) for word, code in words.items()
                 if word.startswith("|") and len(code) == 2}
    if halfwidth != set(range(0xA6, 0xE0)) - {0xB0}:
        raise ValueError("expected the 57 established one-byte codes, excluding B0")
    if words.get("의") != "9540":
        raise ValueError("the fullwidth 의 glyph must remain at 9540")
    with Image.open(font_db / "BISCO.bmp") as source:
        canvas = source.convert("1")
    if canvas.size != (2048, 2048):
        raise ValueError("BISCO font atlas must be 2048x2048")
    glyph_dir = font_db / "byte1FQ3"
    for word, code in words.items():
        if word.startswith("|"):
            continue  # One-byte Korean glyphs are stored in GDATA.CHR.
        if len(code) != 4:
            raise ValueError(f"invalid two-byte code for {word!r}: {code}")
        top, bottom, left, right = return_img_roi(code)
        if len(word) == 1:
            with Image.open(font_db / "byte2비스코" / f"{word}.bmp") as source:
                glyph = source.convert("1")
            if glyph.size != (16, 16):
                raise ValueError(f"invalid full glyph size for {word!r}: {glyph.size}")
        elif len(word) == 2:
            glyph = Image.new("1", (16, 16), 255)
            for index, character in enumerate(word):
                if character == "_":
                    continue
                with Image.open(glyph_dir / f"{character}.bmp") as source:
                    half = source.convert("1")
                if half.size != (8, 16):
                    raise ValueError(f"invalid half glyph size for {character!r}: {half.size}")
                glyph.paste(half, (index * 8, 0))
        else:
            raise ValueError(f"invalid two-byte glyph: {word!r}")
        canvas.paste(glyph, (left, top))
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=WORKSPACE)
    parser.add_argument("--font-db", type=Path, default=FONT_DB)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = args.workspace / "fq3-BISCO.bmp"
    generated = build_font(args.workspace, args.font_db)
    if args.check:
        with Image.open(output) as installed:
            if ImageChops.difference(generated, installed.convert("1")).getbbox():
                raise ValueError(f"generated bitmap differs from {output}")
    else:
        generated.save(output)
    print(output)


if __name__ == "__main__":
    main()
