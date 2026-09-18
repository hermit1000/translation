"""Build a Marine Philt font with frequent Korean glyphs in ADV98 1-byte slots.

The source BMP is never modified. Korean glyphs are read from the ordinary
2-byte Korean font area and written over the corresponding 16x16 Japanese
hiragana glyphs. The MES still stores the compressed 1-byte values, while the
runtime expands those values to the replaced 2-byte glyph slots.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAPPING = Path(__file__).with_name("marine_compact_font_mapping_top20.json")
DEFAULT_SOURCE_BMP = Path(r"C:\work_han\workspace4\ThinDungGeunMo.bmp")
DEFAULT_OUTPUT_BMP = Path(r"C:\work_han\workspace4\mp-ThinDungGeunMo.bmp")
DEFAULT_BASE_TABLE = ROOT / "font_table" / "font_table-kor-jin.json"
DEFAULT_OUTPUT_TABLE = Path(__file__).with_name("font_table-kor-jin-marine-compact.json")


def roi_2byte(code: str) -> tuple[int, int, int, int]:
    value = int(code, 16)
    lead = (value >> 8) & 0xFF
    trail = value & 0xFF
    col = (lead - 0x81) * 2 + 1
    col += trail >= 0x9F
    if trail >= 0x9F:
        row = 33 + trail - 0x9F
    else:
        row = 33 + trail - 0x40
        if trail >= 0x80:
            row -= 1
    return row * 16, row * 16 + 16, col * 16, col * 16 + 16


def load_image(path: Path):
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"could not read BMP: {path}")
    if image.shape[0] < 2048 or image.shape[1] < 2048:
        raise ValueError(f"BMP must be at least 2048x2048: {path} -> {image.shape}")
    return image


def find_code(table: dict[str, str], character: str) -> str:
    lookup = "_" if character == " " and " " not in table.values() else character
    for code, value in table.items():
        if value == lookup and len(code) == 4:
            return code
    raise KeyError(f"no 2-byte Korean glyph code for {character!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--source-bmp", type=Path, default=DEFAULT_SOURCE_BMP)
    parser.add_argument("--output-bmp", type=Path, default=DEFAULT_OUTPUT_BMP)
    parser.add_argument("--base-table", type=Path, default=DEFAULT_BASE_TABLE)
    parser.add_argument("--output-table", type=Path, default=DEFAULT_OUTPUT_TABLE)
    args = parser.parse_args()

    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    base_table = json.loads(args.base_table.read_text(encoding="utf-8"))
    source = load_image(args.source_bmp).copy()
    # This tool intentionally supports only the Marine ThinDungGeunMo font.
    # The same BMP contains both the Korean 2-byte glyph area and the target
    # Japanese hiragana 2-byte glyph area, so no second font asset is mixed in.
    glyphs = source

    output_table = dict(base_table)
    results = []
    for item in mapping["entries"]:
        target = item["character"]
        compact_code = item["code"].upper()
        source_code = find_code(base_table, target)
        sy1, sy2, sx1, sx2 = roi_2byte(source_code)
        # The compressed byte is expanded by the ADV98 text path to this
        # corresponding Japanese 2-byte glyph slot. Replace that 16x16 tile,
        # not the separate 8x16 ASCII/1-byte font strip.
        dy1, dy2, dx1, dx2 = roi_2byte(item["source_sjis"])
        glyph = glyphs[sy1:sy2, sx1:sx2]
        if glyph.shape[0] != 16 or glyph.shape[1] != 16:
            raise ValueError(f"invalid source glyph ROI for {target!r}: {source_code}")
        source[dy1:dy2, dx1:dx2] = glyph
        output_table[compact_code] = target
        results.append({
            "character": target,
            "compact_code": compact_code,
            "source_code": source_code,
            "source_roi": [sx1, sy1, sx2, sy2],
            "target_roi": [dx1, dy1, dx2, dy2],
        })

    args.output_bmp.parent.mkdir(parents=True, exist_ok=True)
    # DOSBox-X's Anex86 font loader expects the original 1-bit BMP layout.
    # cv2.imwrite would silently write an 8-bit grayscale BMP instead, which
    # produces garbage glyphs at runtime. Preserve the 1-bit monochrome form.
    bitmap = Image.fromarray((source > 0).astype("uint8") * 255, mode="L").convert("1")
    bitmap.save(args.output_bmp, format="BMP")
    args.output_table.parent.mkdir(parents=True, exist_ok=True)
    args.output_table.write_text(
        json.dumps(dict(sorted(output_table.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output_bmp": str(args.output_bmp.resolve()),
        "output_table": str(args.output_table.resolve()),
        "mappings": results,
        "note": "1-byte Korean encoding support must be enabled in the Marine MES encoder before using the output table.",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
