#!/usr/bin/env python3
"""Apply verified variable-length translations to an ADV98 MES file."""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from typing import Any

FORBIDDEN_CONTROL_PAIRS = {0x8197, 0x8190, 0x816F, 0x8170}


def encode_adv98_text(text: str) -> bytes:
    """Encode original CP932 text using ADV98's compressed hiragana form."""
    output = bytearray()
    for character in text:
        encoded = character.encode("cp932")
        if len(encoded) == 1:
            value = encoded[0]
            if not 0x2D <= value <= 0x7F:
                raise ValueError(
                    f"single-byte character {character!r} becomes control byte {value:02X}"
                )
            output.append(value)
            continue
        if len(encoded) != 2:
            raise ValueError(f"unsupported CP932 length for {character!r}")
        word = encoded[0] << 8 | encoded[1]
        if word in FORBIDDEN_CONTROL_PAIRS:
            raise ValueError(f"{character!r} is an ADV98 control token")
        compressed = encoded[1] - 0x72
        if encoded[0] == 0x82 and 0x2D <= compressed <= 0x7F:
            output.append(compressed)
        else:
            output.extend(encoded)
    return bytes(output)


def parse_offset(value: str | int) -> int:
    if isinstance(value, int):
        return value
    return int(value, 16)


def load_font_codes(path: Path) -> dict[str, str]:
    if path.suffix.lower() == ".json":
        code_to_char = json.loads(path.read_text(encoding="utf-8"))
        codes: dict[str, str] = {}
        for code, character in code_to_char.items():
            codes.setdefault(character, code)
    else:
        # The project-supplied pickle contains module.font_table.FontTable.
        table = pickle.loads(path.read_bytes())
        codes = dict(table.char2code)
    if " " not in codes and "_" in codes:
        codes[" "] = codes["_"]
    return codes


def encode_translation(text: str, codes: dict[str, str]) -> bytes:
    output = bytearray()
    for character in text:
        code = codes.get(character)
        if code is None:
            raise ValueError(f"character {character!r} is absent from the selected font table")
        raw = bytes.fromhex(code)
        if len(raw) != 2:
            raise ValueError(f"character {character!r} maps to unsupported code {code}")
        first, second = raw
        if not ((0x81 <= first <= 0x9F) or (0xE0 <= first <= 0xFC)):
            raise ValueError(f"character {character!r} maps to non-DBCS lead byte {code}")
        output.extend(raw)
    return bytes(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("translation_json", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    config: dict[str, Any] = json.loads(args.translation_json.read_text(encoding="utf-8"))
    source = Path(config["source"])
    font_table = Path(config["font_table"])
    if source.resolve() == args.output.resolve():
        parser.error("refusing to overwrite the source MES file")

    data = source.read_bytes()
    codes = load_font_codes(font_table)
    replacements = []

    for entry in config["replacements"]:
        start = parse_offset(entry["start"])
        end = parse_offset(entry["end"])
        expected = encode_adv98_text(entry["original"])
        actual = data[start : end + 1]
        if actual != expected:
            raise ValueError(
                f"source mismatch at {start:05X}-{end:05X}: "
                f"expected {expected.hex(' ').upper()}, got {actual.hex(' ').upper()}"
            )
        translated = encode_translation(entry["translation"], codes)
        replacements.append((start, end, translated, entry))

    replacements.sort(key=lambda item: item[0])
    for previous, current in zip(replacements, replacements[1:]):
        if previous[1] >= current[0]:
            raise ValueError("translation ranges overlap")

    rebuilt = data
    applied = []
    for start, end, translated, entry in reversed(replacements):
        old_size = end - start + 1
        rebuilt = rebuilt[:start] + translated + rebuilt[end + 1 :]
        applied.append(
            {
                "start": f"{start:05X}",
                "old_end": f"{end:05X}",
                "original": entry["original"],
                "translation": entry["translation"],
                "new_hex": translated.hex(" ").upper(),
                "old_bytes": old_size,
                "new_bytes": len(translated),
                "delta": len(translated) - old_size,
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rebuilt)
    report = {
        "source": str(source.resolve()),
        "output": str(args.output.resolve()),
        "font_table": str(font_table.resolve()),
        "source_size": len(data),
        "output_size": len(rebuilt),
        "size_delta": len(rebuilt) - len(data),
        "applied": list(reversed(applied)),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
