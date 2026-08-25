#!/usr/bin/env python3
"""Encode one translated ADV98 MES from a structured Korean JSON document."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .translation_codec import encode_adv98_text, encode_translation, load_font_codes
from .decode_mes import decode_mes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    workspace = Path(r"C:\work_han\workspace2")
    parser.add_argument("source_mes", type=Path, nargs="?", default=workspace / "jpn-pc98/MES/OPEN_1.MES")
    parser.add_argument("translation_json", type=Path, nargs="?", default=workspace / "script-pc98/MES/OPEN_1.MES_kor.json")
    parser.add_argument("output_mes", type=Path, nargs="?", default=workspace / "kor-pc98/MES/OPEN_1.MES")
    parser.add_argument("font_table", type=Path, nargs="?", default=Path("font_table/font_table-kor-jin.json"))
    args = parser.parse_args()

    document = json.loads(args.translation_json.read_text(encoding="utf-8"))
    source = args.source_mes.read_bytes()
    if hashlib.sha256(source).hexdigest() != document["source_sha256"]:
        raise ValueError("source MES SHA-256 does not match the translation JSON")
    codes = load_font_codes(args.font_table)
    replacements: list[tuple[int, int, bytes]] = []
    catalog = json.loads((Path(__file__).with_name("macro_catalog.json")).read_text(encoding="utf-8"))["macros"]
    overrides_path = Path(__file__).with_name("file_macro_overrides.json")
    if overrides_path.exists():
        overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
        for slot, values in overrides.get(args.source_mes.name, {}).items():
            catalog[slot] = {**catalog.get(slot, {}), **values}
    command_overrides = {
        int(record["offset"], 16): record.get("translation")
        for record in document["records"]
        if record.get("type") == "command" and record.get("name") == "CALL_BUILTIN"
    }
    for record in document["records"]:
        translation = record.get("translation")
        if record.get("type") != "text" or translation is None:
            continue
        start = int(record["offset"], 16)
        end = int(record["end"], 16)
        original = record["original"]
        actual = source[start : end + 1]
        # A few ending-screen records contain bytes that are not decodable
        # as Shift-JIS and therefore appear as U+FFFD in *_info.json.  The
        # offset/end range still identifies the source bytes unambiguously;
        # skip re-encoding only for those records and retain the raw range.
        if "\ufffd" in original:
            if not actual:
                raise ValueError(f"source range is empty at {start:05X}-{end:05X}")
        else:
            expected = encode_adv98_text(original)
            if actual != expected:
                raise ValueError(f"source mismatch at {start:05X}-{end:05X}")
        replacements.append((start, end, encode_translation(translation, codes)))

    tokens = decode_mes(source)
    for index, token in enumerate(tokens):
        if token.get("type") != "command" or token.get("value") != "CALL_BUILTIN":
            continue
        if index + 1 >= len(tokens) or tokens[index + 1].get("type") != "argument":
            continue
        slot = f'{tokens[index + 1]["value"]:02X}'
        macro = catalog.get(slot)
        if not macro or macro.get("category") not in {"speaker", "punctuation", "spacing"}:
            continue
        translation = command_overrides.get(token["offset"]) or macro.get("translation")
        if translation is None:
            continue
        start = token["offset"]
        end = tokens[index + 1]["offset"] + tokens[index + 1]["size"] - 1
        replacements.append((start, end, encode_translation(translation, codes)))

    # Also scan raw BA calls directly. This covers macro calls whose argument
    # is not exposed as the immediately following lexical token by older
    # decoders and guarantees catalog speaker/punctuation expansion.
    for index, value in enumerate(source[:-1]):
        if value != 0xBA:
            continue
        argument_size = 1
        argument = source[index + 1]
        if argument == 0x28 and index + 2 < len(source):
            slot = f"{source[index + 2]:02X}"
            argument_size = 2
        elif 0x23 <= argument <= 0x27:
            slot = f"{argument - 0x23:02X}"
        else:
            continue
        macro = catalog.get(slot)
        if not macro or macro.get("category") not in {"speaker", "punctuation", "spacing"}:
            continue
        translation = command_overrides.get(index) or macro.get("translation")
        if translation is None:
            continue
        end = index + argument_size
        if any(start <= index <= old_end or start <= end <= old_end for start, old_end, _ in replacements):
            continue
        replacements.append((index, end, encode_translation(translation, codes)))

    replacements.sort()
    for previous, current in zip(replacements, replacements[1:]):
        if previous[1] >= current[0]:
            raise ValueError("translation ranges overlap")
    rebuilt = source
    for start, end, translated in reversed(replacements):
        rebuilt = rebuilt[:start] + translated + rebuilt[end + 1 :]
    args.output_mes.parent.mkdir(parents=True, exist_ok=True)
    args.output_mes.write_bytes(rebuilt)
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
