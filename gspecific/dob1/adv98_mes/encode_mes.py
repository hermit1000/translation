#!/usr/bin/env python3
"""Encode one translated ADV98 MES from a structured Korean JSON document."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from .translation_codec import encode_adv98_text, encode_translation, load_font_codes
    from .decode_mes import decode_mes
except ImportError:
    from translation_codec import encode_adv98_text, encode_translation, load_font_codes
    from decode_mes import decode_mes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    workspace = Path(r"C:\work_han\workspace2")
    parser.add_argument("source_mes", type=Path, nargs="?", default=workspace / "jpn-pc98/MES/OPEN_1.MES")
    parser.add_argument("translation_json", type=Path, nargs="?", default=workspace / "script-pc98/MES/OPEN_1.MES_kor.json")
    parser.add_argument("output_mes", type=Path, nargs="?", default=workspace / "kor-pc98/MES/OPEN_1.MES")
    parser.add_argument("font_table", type=Path, nargs="?", default=Path("font_table/font_table-kor-jin.json"))
    parser.add_argument("--debug-offset", help="print replacement details for one source offset (hex)")
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

    # Some ADV98 records use a punctuation macro immediately before a
    # BC A2 0C 23 cursor/state command.  Replacing that three-byte macro with
    # a raw font glyph changes the runtime state and makes the next segment
    # appear shifted or disappear.  Keep the original macro at these
    # boundaries; ordinary punctuation macros are still translated below.
    def preserve_boundary_macro(start: int, end: int) -> bool:
        # Kept as a hook for future engine-specific boundaries.  The
        # 004F1 compressed-pair fix below now makes raw Korean punctuation
        # safe, so punctuation macros must be translated to 81 44/81 43.
        return False

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

    credit_ranges: list[tuple[int, int]] = []
    if args.source_mes.name.upper() == "000067.MES" and document.get("credit_layout") == "compact-v1":
        credit_translations = {
            record["offset"]: record.get("translation", "")
            for record in document.get("extra_texts", [])
        }
        indent = "        : "
        credit_blocks = [
            (0x1281, 0x12BA, [
                ("SCENARIO", None),
                (indent + "RUSH-TEAM", None),
                (indent, "012B1"),
            ]),
            (0x12DE, 0x1304, [
                ("SYSTEM PRODUCER", None),
                (indent, "012FB"),
            ]),
            (0x132A, 0x13C6, [
                ("TECHNICAL PROGRAM", None),
                (indent, "01349"),
                (indent, "0136A"),
                (indent, "01384"),
                (indent, "013A4"),
                (indent, "013C3"),
            ]),
            (0x143E, 0x14C6, [
                ("GRAPHICS PRODUCE", None),
                (indent + "TOMBOY", None),
                (indent, "01476"),
                ("CHARACTER DESIGN", None),
                (indent, "014A0"),
                ("GRAPHICS", None),
                (indent, "014BF"),
            ]),
            (0x14EC, 0x152F, [
                ("GRAPHICS DESIGN", None),
                (indent + "R-FRONTIER", None),
                (indent, "01528"),
            ]),
            (0x1554, 0x15F6, [
                ("GRAPHICS EDIT", None),
                (indent, "01567"),
                (indent + "VOGUE", None),
                (indent, "015A3"),
                (indent, "015C1"),
                (indent, "015D9"),
                (indent + "GEO", None),
            ]),
            (0x166E, 0x16C3, [
                ("SOUND PRODUCE", None),
                (indent + "Muse", None),
                ("MUSIC & SOUND", None),
                (indent + "RAY", None),
                (indent + "MARINA", None),
            ]),
            (0x16E5, 0x1799, [
                ("TECHNICAL DIRECTOR", None),
                (indent, "01704"),
                ("TECHNICAL ADVISER", None),
                (indent, "0172D"),
                (indent, "0174B"),
                ("ASSISTANT DIRECTOR", None),
                (indent, "01774"),
                (indent, "01792"),
            ]),
            (0x17C6, 0x1839, [
                ("PACKAGE DESIGN", None),
                (indent, "017D9"),
                ("DIRECTOR", None),
                (indent + "RUSH-TEAM", None),
                (indent, "01811"),
                ("PRODUCER", None),
                (indent, "01830"),
            ]),
        ]
        for start, end, lines in credit_blocks:
            encoded_lines = []
            for ascii_text, translation_offset in lines:
                line = b"\x21" + ascii_text.encode("ascii") + b"\x00"
                if translation_offset is not None:
                    translation = credit_translations.get(translation_offset, "")
                    if not translation:
                        raise ValueError(f"missing credit translation at {translation_offset}")
                    line += encode_translation(translation, codes)
                encoded_lines.append(line)
            replacements.append((start, end, b"\xA5".join(encoded_lines)))
            credit_ranges.append((start, end))

    for record in document.get("extra_texts", []):
        if record.get("translation") in (None, ""):
            continue
        start, end = int(record["offset"], 16), int(record["end"], 16)
        if any(block_start <= start and end <= block_end for block_start, block_end in credit_ranges):
            continue
        overlaps = [(a, b, payload) for a, b, payload in replacements if a <= end and start <= b]
        if overlaps:
            # Prefer a manually supplied full-range extra record over a
            # shorter duplicate metadata record (e.g. 007DD vs 007DF).
            if all(start <= a and b <= end for a, b, _ in overlaps):
                replacements = [r for r in replacements if r not in overlaps]
            else:
                continue
        replacements.append((start, end, encode_translation(record["translation"], codes)))
    sidecar = Path(__file__).with_name(f"extra_{args.source_mes.stem}.json")
    if sidecar.exists():
        for record in json.loads(sidecar.read_text(encoding="utf-8")):
            start, end = int(record["offset"], 16), int(record["end"], 16)
            if any(a <= end and start <= b for a, b, _ in replacements):
                continue
            replacements.append((start, end, encode_translation(record["translation"], codes)))

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
        if preserve_boundary_macro(start, end):
            continue
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
        if preserve_boundary_macro(index, end):
            continue
        if any(start <= index <= old_end or start <= end <= old_end for start, old_end, _ in replacements):
            continue
        replacements.append((index, end, encode_translation(translation, codes)))

    replacements.sort()
    # Inventory/choice labels in these two room scripts are emitted from a
    # small unindexed MES text block rather than dialogue/overlay metadata.
    # Translate only the known label occurrences; identical words elsewhere
    # remain untouched.
    choice_labels = {
        "000048.MES": {0xFB0: (bytes.fromhex("96 7B"), bytes.fromhex("92 44")),
                       0xFB3: (bytes.fromhex("95 95 93 9B"), bytes.fromhex("8D BE 9395"))},
        "000049.MES": {0xEF7: (bytes.fromhex("96 7B"), bytes.fromhex("92 44")),
                       0xEFA: (bytes.fromhex("95 95 93 9B"), bytes.fromhex("8D BE 9395"))},
        "000050.MES": {0x030: (bytes.fromhex("96 7B"), bytes.fromhex("92 44")),
                       0x039: (bytes.fromhex("93 FA 8B 4C"), bytes.fromhex("90 CD 89 82")),
                       0x044: (bytes.fromhex("95 95 93 9B"), bytes.fromhex("8D BE 9395")),
                       0x04F: (bytes.fromhex("8E CA 90 5E"), bytes.fromhex("8E 87 91 98")),
                       0x069: (bytes.fromhex("93 FA 8B 4C"), bytes.fromhex("90 CD 89 82"))},
        "000051.MES": {0x030: (bytes.fromhex("96 7B"), bytes.fromhex("92 44")),
                       0x039: (bytes.fromhex("93 FA 8B 4C"), bytes.fromhex("90 CD 89 82")),
                       0x044: (bytes.fromhex("95 95 93 9B"), bytes.fromhex("8D BE 9395")),
                       0x04F: (bytes.fromhex("8E CA 90 5E"), bytes.fromhex("8E 87 91 98")),
                       0x069: (bytes.fromhex("93 FA 8B 4C"), bytes.fromhex("90 CD 89 82"))},
    }
    for start, (old, new) in choice_labels.get(args.source_mes.name.upper(), {}).items():
        if source[start:start + len(old)] == old and not any(a <= start <= b for a, b, _ in replacements):
            replacements.append((start, start + len(old) - 1, new))
    replacements.sort()
    # 000046/004F1 contains two adjacent compressed records whose Shift-JIS
    # continuation bytes are split out of the metadata (004FE and 00500).
    # Replacing only the lead bytes leaves A4/A3 in the stream, producing a
    # missing Korean syllable and Japanese-looking punctuation.  Consume the
    # complete four-byte pair as one replacement.
    if args.source_mes.name.upper() == "000046.MES":
        first = next((r for r in replacements if r[0] == 0x4FE), None)
        second = next((r for r in replacements if r[0] == 0x500), None)
        if first and second and first[1] == 0x4FE and second[1] == 0x500:
            replacements.remove(first)
            replacements.remove(second)
            replacements.append((0x4FE, 0x501, first[2] + second[2]))
            replacements.sort()
    if args.debug_offset:
        target = int(args.debug_offset, 16)
        delta = 0
        for start, end, replacement in replacements:
            if start <= target <= end or start == target:
                print(f"DEBUG source={start:05X}-{end:05X} output={start + delta:05X} bytes={replacement.hex(' ').upper()}")
            delta += len(replacement) - (end - start + 1)
    for previous, current in zip(replacements, replacements[1:]):
        if previous[1] >= current[0]:
            raise ValueError(
                f"translation ranges overlap: {previous[0]:05X}-{previous[1]:05X} "
                f"and {current[0]:05X}-{current[1]:05X}"
            )
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
