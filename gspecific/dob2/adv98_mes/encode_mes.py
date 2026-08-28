#!/usr/bin/env python3
"""Encode one DOB2 MES using its info/lang translation documents."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from gspecific.dob1.adv98_mes.translation_codec import encode_translation, load_font_codes


KEEP_ORIGINAL = "@keep"
DISPLAY_LINE_CELLS = 31


def trim_wrap_boundary_spaces(value: str, width: int = DISPLAY_LINE_CELLS) -> str:
    """Remove spaces at ADV98's 31st, 61st, ... editable cells."""
    output: list[str] = []
    cells = 0
    for character in value:
        if character == " " and cells > 0 and cells % (width - 1) == 0:
            continue
        output.append(character)
        cells += 1
    return "".join(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_mes", type=Path)
    parser.add_argument("info_json", type=Path)
    parser.add_argument("lang_json", type=Path)
    parser.add_argument("output_mes", type=Path)
    parser.add_argument(
        "font_table",
        type=Path,
        nargs="?",
        default=Path("font_table/font_table-kor-jin.json"),
    )
    args = parser.parse_args()

    source = args.source_mes.read_bytes()
    info = json.loads(args.info_json.read_text(encoding="utf-8"))
    lang = json.loads(args.lang_json.read_text(encoding="utf-8"))
    if hashlib.sha256(source).hexdigest() != info["source_sha256"]:
        raise ValueError("source MES SHA-256 does not match info JSON")
    if lang.get("source_info") != args.info_json.name:
        raise ValueError("lang JSON refers to a different info JSON")

    records = {record.get("offset"): record for record in info["records"]}
    codes = None
    replacements: list[tuple[int, int, bytes]] = []
    editable_entries = [
        *(lang.get("dialogue_groups", [])),
        *(lang.get("overlay_texts", [])),
    ]
    for entry in editable_entries:
        offset = entry.get("offset")
        record = records.get(offset)
        if not record or record.get("type") != "text":
            raise ValueError(f"unknown text record: {offset}")
        dialogue = str(entry.get("id", "")).startswith("dialogue:")
        if entry.get("original") != record.get("original"):
            raise ValueError(f"original mismatch at {offset}")
        start = int(record["offset"], 16)
        end = int(record["end"], 16)
        expected = bytes.fromhex(record["raw_hex"])
        if source[start : end + 1] != expected:
            raise ValueError(f"source bytes mismatch at {start:05X}-{end:05X}")
        translation = entry.get("translation")
        if not translation:
            entry["status"] = (
                "incomplete: untranslated dialogue" if dialogue else "incomplete: untranslated overlay"
            )
            continue
        if translation == KEEP_ORIGINAL:
            entry["status"] = "passed"
            continue
        if codes is None:
            codes = load_font_codes(args.font_table)
        try:
            # Normalize only the encoded MES value.  Keep the editable JSON
            # exactly as entered so later translation work does not inherit
            # shifted line-boundary spaces.
            encoded = encode_translation(trim_wrap_boundary_spaces(translation), codes)
        except ValueError as exc:
            entry["status"] = f"error: {exc}"
            raise
        replacements.append((start, end, encoded))
        entry["status"] = "passed"

    replacements.sort()
    for previous, current in zip(replacements, replacements[1:]):
        if previous[1] >= current[0]:
            raise ValueError("translation ranges overlap")

    rebuilt = source
    for start, end, encoded in reversed(replacements):
        rebuilt = rebuilt[:start] + encoded + rebuilt[end + 1 :]
    args.output_mes.parent.mkdir(parents=True, exist_ok=True)
    args.output_mes.write_bytes(rebuilt)
    args.lang_json.write_text(json.dumps(lang, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output_mes.resolve()),
                "source_size": len(source),
                "output_size": len(rebuilt),
                "replacements": len(replacements),
                "size_delta": len(rebuilt) - len(source),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
