"""Replace 57 FQ3 GDATA slots, preserving B0's save-slot bar."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from .gdata_codec import compress, decompress


def build_bytes(workspace: Path) -> bytes:
    source = (workspace / "jpn-pc98" / "GDATA.CHR").read_bytes()
    decoded = bytearray(decompress(source))
    words = json.loads((workspace / "script-pc98" / "custom_word.json").read_text(encoding="utf-8"))
    font_dir = workspace.parent / "font_update_db" / "byte1FQ3"
    glyphs: dict[int, str] = {}
    for text, code_hex in words.items():
        if not (text.startswith("|") and len(text) == 2 and len(code_hex) == 2):
            continue
        code = int(code_hex, 16)
        if 0xA6 <= code <= 0xDF and code != 0xB0:
            if code in glyphs:
                raise ValueError(f"duplicate halfwidth code {code:02X}")
            glyphs[code] = text[1]
    expected_codes = set(range(0xA6, 0xE0)) - {0xB0}
    if set(glyphs) != expected_codes:
        raise ValueError("custom_word.json must map 57 A6-DF glyphs, excluding B0")

    for code, letter in glyphs.items():
        path = font_dir / f"{letter}.bmp"
        with Image.open(path) as image:
            if image.size != (8, 16):
                raise ValueError(f"expected 8x16 bitmap: {path}")
            bitmap = image.convert("1")
            rows = bytes(sum((1 << (7 - x)) for x in range(8)
                             if bitmap.getpixel((x, y)) == 0) for y in range(16))
        # 258DC..25916 maps raw A6..DF to IDs 29..62; B0/33 stays original.
        at = 0x8400 + (code - 0x7D) * 16
        decoded[at:at + 16] = rows
    result = compress(bytes(decoded))
    if decompress(result) != bytes(decoded):
        raise ValueError("GDATA.CHR verification failed")
    return result
