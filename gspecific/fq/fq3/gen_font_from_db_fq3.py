"""Build FQ3's BISCO font from the fixed custom word map and glyph atlas."""

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
    with Image.open(font_db / "fq3-ThinDungGeunMo.bmp") as source:
        custom = source.convert("1")
    if canvas.size != (2048, 2048) or custom.size != canvas.size:
        raise ValueError("font atlases must be 2048x2048")
    for word, code in words.items():
        if word.startswith("|"):
            continue  # One-byte Korean glyphs are stored in GDATA.CHR.
        if len(code) != 4:
            raise ValueError(f"invalid two-byte code for {word!r}: {code}")
        top, bottom, left, right = return_img_roi(code)
        canvas.paste(custom.crop((left, top, right, bottom)), (left, top))
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
