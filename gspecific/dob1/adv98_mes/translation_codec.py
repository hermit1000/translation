#!/usr/bin/env python3
"""Apply verified variable-length translations to an ADV98 MES file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# Keep the legacy direct-script entry point working from any directory.
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from mes.adv_common.text import (
    FORBIDDEN_CONTROL_PAIRS, encode_adv98_text, encode_translation,
    load_font_codes, parse_offset,
)


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
