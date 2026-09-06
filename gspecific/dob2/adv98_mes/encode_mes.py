#!/usr/bin/env python3
"""Encode one DOB2 MES using its info/lang translation documents."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from gspecific.adv_common.patches import apply_replacements
from gspecific.adv_common.text import (
    encode_adv98_text,
    encode_translation,
    load_font_codes,
)


KEEP_ORIGINAL = "@keep"
DISPLAY_LINE_CELLS = 31
PRESERVED_ASCII_PREFIXES = ("se &", "se $", "se '")


def normalize_control08_speaker_translation(value: str) -> str:
    """Remove decoder artifacts before a CONTROL_08 speaker label."""
    opening_positions = [
        position for mark in ("[", "〔") if (position := value.find(mark)) >= 0
    ]
    if opening_positions:
        return value[min(opening_positions) :]
    if value.startswith("め") and any(mark in value[1:] for mark in ("]", "〕")):
        return "〔" + value[1:]
    return value


def trim_wrap_boundary_spaces(value: str, width: int | None = None) -> str:
    """Remove spaces at the first cell after each configured display line."""
    if width is None:
        width = DISPLAY_LINE_CELLS
    output: list[str] = []
    cells = 0
    for character in value:
        if character == " " and cells > 0 and cells % (width - 1) == 0:
            continue
        output.append(character)
        # ADV98 advances one text cell per displayed character, including
        # full-width Japanese/Korean glyphs. The encoded byte width does not
        # determine the 31-cell dialogue-window position.
        cells += 1
    return "".join(output)


def encode_record_translation(
    original: str, translation: str, codes: dict[str, str], raw: bytes | None = None,
    *, width: int = DISPLAY_LINE_CELLS,
    speaker_repairs: bool = True,
) -> bytes:
    """Preserve DOB2 inline ASCII controls and encode only their display text."""
    for prefix in PRESERVED_ASCII_PREFIXES:
        if original.startswith(prefix) and translation.startswith(prefix):
            display_text = trim_wrap_boundary_spaces(translation[len(prefix) :], width)
            return prefix.encode("ascii") + encode_translation(display_text, codes)
    if not speaker_repairs:
        return encode_translation(trim_wrap_boundary_spaces(translation, width), codes)
    if raw is not None and len(raw) >= 3 and raw[1:3] == bytes.fromhex("81 6D"):
        # CONTROL_08's one-byte speaker ID precedes the source opening bracket.
        display_text = normalize_control08_speaker_translation(translation)
        return raw[:1] + encode_translation(trim_wrap_boundary_spaces(display_text, width), codes)
    # After CONTROL_08, the one-byte compressed glyph before ``［`` is the
    # speaker-ID parameter, not dialogue text. Preserve it for the engine,
    # while replacing the visible Japanese speaker label with the translation.
    speaker_parameter = original[0].encode("cp932") if original else b""
    compressed_parameter = (
        len(speaker_parameter) == 2
        and speaker_parameter[0] == 0x82
        and 0x2D <= speaker_parameter[1] - 0x72 <= 0x7F
    )
    if len(original) >= 2 and original[1] == "［" and compressed_parameter:
        return encode_adv98_text(original[0]) + encode_translation(
            trim_wrap_boundary_spaces(translation, width), codes
        )
    # In the complementary form, CONTROL_08 has already consumed the lead
    # byte of a two-byte ``［`` parameter (81), leaving its 6D trail byte at
    # the start of this text record: ``めシーラ］``. Keep that trail byte and
    # remove only the duplicate translated opening bracket.
    if compressed_parameter and "［" not in original and "］" in original:
        display_text = translation
        if translation.startswith(("[", "〔")):
            closing = next((mark for mark in ("]", "〕") if mark in translation[1:]), None)
            if closing is not None:
                close_index = translation.index(closing, 1)
                display_text = translation[1:close_index] + "]" + translation[close_index + 1 :]
        return encode_adv98_text(original[0]) + encode_translation(
            trim_wrap_boundary_spaces(display_text, width), codes
        )
    bracket_positions = [original.find(mark) for mark in ("［", "］", "[", "]")]
    bracket_positions = [position for position in bracket_positions if position >= 0]
    if bracket_positions:
        prefix_end = min(bracket_positions)
        prefix = original[:prefix_end]
        if prefix and any(ord(character) >= 128 for character in prefix):
            # Japanese text before a speaker bracket is a stray/merged marker;
            # omit it from the encoded dialogue as well as visible text.
            display_text = translation[len(prefix) :] if translation.startswith(prefix) else translation
            return encode_translation(trim_wrap_boundary_spaces(display_text, width), codes)
    return encode_translation(trim_wrap_boundary_spaces(translation, width), codes)


def main(*, width: int = DISPLAY_LINE_CELLS, speaker_repairs: bool = True) -> int:
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
            if (
                speaker_repairs
                and start > 0
                and source[start - 1 : start + 1] == bytes.fromhex("81 6D")
                and record["original"].startswith("め")
                and "［" not in record["original"]
                and "］" in record["original"]
            ):
                # The source record starts at the 6D trail byte of an 81 6D
                # opening bracket. Expand the replacement by one byte so the
                # translated 〔 glyph replaces the complete bracket pair.
                translation = normalize_control08_speaker_translation(translation)
                translation = translation.translate(str.maketrans({"[": "〔", "]": "〕"}))
                encoded = encode_translation(trim_wrap_boundary_spaces(translation, width), codes)
                start -= 1
            else:
                encoded = encode_record_translation(record["original"], translation, codes, expected,
                                                    width=width, speaker_repairs=speaker_repairs)
        except ValueError as exc:
            entry["status"] = f"error: {exc}"
            raise
        replacements.append((start, end, encoded))
        entry["status"] = "passed"

    replacements.sort()
    for previous, current in zip(replacements, replacements[1:]):
        if previous[1] >= current[0]:
            raise ValueError("translation ranges overlap")

    rebuilt = apply_replacements(source, replacements)
    if args.source_mes.suffix.upper() == ".CAL" and len(rebuilt) > len(source):
        raise ValueError(
            f"encoded CAL exceeds its fixed source allocation: "
            f"{len(rebuilt)} > {len(source)} bytes"
        )
    args.output_mes.parent.mkdir(parents=True, exist_ok=True)
    args.output_mes.write_bytes(rebuilt)
    lang_text = json.dumps(lang, ensure_ascii=False, indent=2) + "\n"
    args.lang_json.write_text(
        lang_text.replace("\n", "\r\n"), encoding="utf-8", newline=""
    )
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
