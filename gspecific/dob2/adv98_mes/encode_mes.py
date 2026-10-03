#!/usr/bin/env python3
"""Encode one DOB2 MES using its info/lang translation documents."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mes.adv_common.patches import apply_replacements, write_patch_manifest
from mes.adv_common.text import (
    encode_adv98_text,
    encode_translation,
    load_font_codes,
)


KEEP_ORIGINAL = "@keep"
DISPLAY_LINE_CELLS = 31
PRESERVED_ASCII_PREFIXES = ("se &", "se $", "se '")


def leading_quoted_control(raw: bytes | None) -> bytes:
    """Return a leading quoted ADV98 layout command, if present.

    Older Dracula info files folded quoted layout commands such as
    ``"P 2 33 0"`` into the following text record.  The command is source
    structure, not editable display text, so preserve its original bytes
    while encoding only the normalized translation body.
    """
    if not raw or raw[:1] != b'"':
        return b""
    closing = raw.find(b'"', 1)
    if closing < 0:
        return b""
    command = raw[1:closing]
    if not command or any(value < 0x20 or value > 0x7E for value in command):
        return b""
    return raw[: closing + 1]


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


def trim_wrap_boundary_spaces(
    value: str, width: int | None = None, *, initial_cells: int = 0,
    preserve_boundary_runs: bool = False,
) -> str:
    """Remove spaces at the first cell after each configured display line."""
    if width is None:
        width = DISPLAY_LINE_CELLS
    output: list[str] = []
    cells = initial_cells
    for index, character in enumerate(value):
        if (
            character == " "
            and cells > 0
            and cells % (width - 1) == 0
            and not (preserve_boundary_runs and index + 1 < len(value) and value[index + 1] == " ")
        ):
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
    initial_cells: int = 0,
    one_byte_codes: dict[str, int] | None = None,
    preserve_boundary_runs: bool = False,
) -> bytes:
    """Preserve DOB2 inline ASCII controls and encode only their display text."""
    quoted_control = leading_quoted_control(raw)
    if quoted_control:
        return quoted_control + encode_translation(
            trim_wrap_boundary_spaces(
                translation, width, initial_cells=initial_cells,
                preserve_boundary_runs=preserve_boundary_runs,
            ),
            codes,
            one_byte_codes=one_byte_codes,
        )
    for prefix in PRESERVED_ASCII_PREFIXES:
        if original.startswith(prefix) and translation.startswith(prefix):
            display_text = trim_wrap_boundary_spaces(
                translation[len(prefix) :], width, initial_cells=initial_cells,
                preserve_boundary_runs=preserve_boundary_runs,
            )
            return prefix.encode("ascii") + encode_translation(display_text, codes, one_byte_codes=one_byte_codes)
    if not speaker_repairs:
        return encode_translation(
            trim_wrap_boundary_spaces(translation, width, initial_cells=initial_cells,
                                      preserve_boundary_runs=preserve_boundary_runs),
            codes, one_byte_codes=one_byte_codes,
        )
    if raw is not None and len(raw) >= 3 and raw[1:3] == bytes.fromhex("81 6D"):
        # CONTROL_08's one-byte speaker ID precedes the source opening bracket.
        display_text = normalize_control08_speaker_translation(translation)
        return raw[:1] + encode_translation(
            trim_wrap_boundary_spaces(display_text, width, initial_cells=initial_cells,
                                      preserve_boundary_runs=preserve_boundary_runs),
            codes, one_byte_codes=one_byte_codes,
        )
    # After CONTROL_08, the one-byte compressed glyph before ``［`` is the
    # speaker-ID parameter, not dialogue text. Preserve it for the engine,
    # while replacing the visible Japanese speaker label with the translation.
    speaker_parameter = original[0].encode("cp932") if original else b""
    compressed_parameter = (
        len(speaker_parameter) == 2
        and speaker_parameter[0] == 0x82
        and 0x2D <= speaker_parameter[1] - 0x72 <= 0x7F
    )
    # Some non-dialogue records begin with a small kana that is actually the
    # one-byte ADV98 parameter emitted before the visible text.  The decoder
    # exposes that parameter as a leading character (for example ``ょこの``),
    # but the engine still consumes the byte at runtime.  Preserve the
    # parameter while replacing the visible text, otherwise the first
    # translated glyph is consumed and disappears on screen.
    if compressed_parameter and original[0] in "ぁぃぅぇぉっゃゅょゎ":
        return encode_adv98_text(original[0]) + encode_translation(
            trim_wrap_boundary_spaces(translation, width, initial_cells=initial_cells,
                                      preserve_boundary_runs=preserve_boundary_runs),
            codes, one_byte_codes=one_byte_codes,
        )
    if len(original) >= 2 and original[1] == "［" and compressed_parameter:
        return encode_adv98_text(original[0]) + encode_translation(
            trim_wrap_boundary_spaces(translation, width, initial_cells=initial_cells,
                                      preserve_boundary_runs=preserve_boundary_runs),
            codes, one_byte_codes=one_byte_codes,
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
            trim_wrap_boundary_spaces(display_text, width, initial_cells=initial_cells,
                                      preserve_boundary_runs=preserve_boundary_runs),
            codes, one_byte_codes=one_byte_codes,
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
            return encode_translation(
                trim_wrap_boundary_spaces(display_text, width, initial_cells=initial_cells,
                                          preserve_boundary_runs=preserve_boundary_runs),
                codes, one_byte_codes=one_byte_codes,
            )
    return encode_translation(
        trim_wrap_boundary_spaces(translation, width, initial_cells=initial_cells,
                                  preserve_boundary_runs=preserve_boundary_runs),
        codes, one_byte_codes=one_byte_codes,
    )


def main(*, width: int = DISPLAY_LINE_CELLS, speaker_repairs: bool = True,
         preprocess_lang=None, postprocess_lang=None,
         postprocess_output=None,
         default_marine_remap=None,
         preserve_boundary_runs: bool = False) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch-manifest", type=Path, help="record exact allowed byte replacements for validation")
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
    parser.add_argument("--marine-remap", type=Path, default=default_marine_remap)
    args = parser.parse_args()
    if args.patch_manifest and args.patch_manifest.resolve() in {
        p.resolve() for p in (args.source_mes, args.info_json, args.lang_json, args.output_mes, args.font_table)
    }:
        raise ValueError("patch manifest must use a separate path")

    source = args.source_mes.read_bytes()
    info = json.loads(args.info_json.read_text(encoding="utf-8"))
    lang = json.loads(args.lang_json.read_text(encoding="utf-8"))
    preprocess_result = preprocess_lang(info, lang) if preprocess_lang is not None else None
    if hashlib.sha256(source).hexdigest() != info["source_sha256"]:
        raise ValueError("source MES SHA-256 does not match info JSON")
    if lang.get("source_info") != args.info_json.name:
        raise ValueError("lang JSON refers to a different info JSON")

    records = {record.get("offset"): record for record in info["records"]}
    codes = None
    one_byte_codes = None
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
            if args.marine_remap is not None:
                from mes.adv_common.text import load_marine_remap
                one_byte_codes = load_marine_remap(args.marine_remap)
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
                encoded = encode_translation(
                    trim_wrap_boundary_spaces(translation, width,
                                              preserve_boundary_runs=preserve_boundary_runs),
                    codes,
                    one_byte_codes=one_byte_codes,
                )
                start -= 1
            else:
                encoded = encode_record_translation(
                    record["original"], translation, codes, expected,
                    width=width,
                    speaker_repairs=speaker_repairs,
                    initial_cells=int(entry.get("_display_prefix_cells", 0)),
                    one_byte_codes=one_byte_codes,
                    preserve_boundary_runs=preserve_boundary_runs,
                )
        except ValueError as exc:
            entry["status"] = f"error: {exc}"
            raise
        replacements.append((start, end, encoded))
        entry["status"] = "passed"

    for start, end in (preprocess_result or {}).get("skip_ranges", []):
        replacements.append((start, end, b""))

    replacements.sort()
    for previous, current in zip(replacements, replacements[1:]):
        if previous[1] >= current[0]:
            raise ValueError("translation ranges overlap")

    rebuilt = apply_replacements(source, replacements)
    if postprocess_output is not None:
        rebuilt = postprocess_output(info, rebuilt)
    if args.source_mes.suffix.upper() == ".CAL" and len(rebuilt) > len(source):
        raise ValueError(
            f"encoded CAL exceeds its fixed source allocation: "
            f"{len(rebuilt)} > {len(source)} bytes"
        )
    if args.patch_manifest:
        write_patch_manifest(args.patch_manifest, source, rebuilt, replacements)
    args.output_mes.parent.mkdir(parents=True, exist_ok=True)
    args.output_mes.write_bytes(rebuilt)
    if postprocess_lang is not None:
        postprocess_lang(info, lang)
    lang_text = json.dumps(lang, ensure_ascii=False, indent=2) + "\n"
    args.lang_json.write_text(
        lang_text.replace("\n", "\r\n"), encoding="utf-8", newline=""
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
