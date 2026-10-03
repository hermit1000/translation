#!/usr/bin/env python3
"""Encode translated Necronomicon SYSTEM.MEC menu strings."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

try:
    from mes.adv_common.patches import apply_replacements
except ModuleNotFoundError:  # Support direct execution from the code folder.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from mes.adv_common.patches import apply_replacements

try:
    from .system_mec import encode_menu_text
except ImportError:  # Support direct execution: python encode_system_mec.py
    from system_mec import encode_menu_text


def encode_one(
    source_path: Path,
    info_path: Path,
    lang_path: Path,
    output_path: Path,
    font_table: Path,
    compact_remap: Path,
) -> None:
    source = source_path.read_bytes()
    info = json.loads(info_path.read_text(encoding="utf-8"))
    lang = json.loads(lang_path.read_text(encoding="utf-8"))
    if hashlib.sha256(source).hexdigest() != info["source_sha256"]:
        raise ValueError(f"source {source_path.name} SHA-256 does not match info JSON")
    if lang.get("source_info") != info_path.name:
        raise ValueError("lang JSON refers to a different info JSON")

    records = {record["offset"]: record for record in info["records"]}
    replacements = []
    for entry in lang.get("entries", []):
        if entry.get("status") == "passed" or not entry.get("translation"):
            continue
        record = records.get(entry.get("offset"))
        if not record or entry.get("original") != record.get("original"):
            raise ValueError(f"unknown or mismatched MEC entry: {entry.get('offset')}")
        if record.get("variable_tokens"):
            encoded_parts = []
            value = entry["translation"]
            for placeholder, raw_token_hex in record["variable_tokens"].items():
                if placeholder not in value:
                    raise ValueError(
                        f"missing variable token {placeholder} at {entry['offset']}"
                    )
                prefix, value = value.split(placeholder, 1)
                encoded_parts.append(encode_menu_text(prefix, font_table, compact_remap))
                encoded_parts.append(bytes.fromhex(raw_token_hex))
            encoded_parts.append(encode_menu_text(value, font_table, compact_remap))
            encoded = b"".join(encoded_parts)
        else:
            encoded = encode_menu_text(entry["translation"], font_table, compact_remap)
        start = int(record["offset"], 16)
        end = int(record["end"], 16)
        capacity = end - start + 1
        if len(encoded) < capacity:
            padding = capacity - len(encoded)
            if record.get("padding_mode") == "compact-space":
                encoded += encode_menu_text(" " * padding, font_table, compact_remap)
                padding = 0
            if padding % 2:
                encoded += b" "
                padding -= 1
            encoded += "　".encode("cp932") * (padding // 2)
        if len(encoded) != capacity:
            raise ValueError(
                f"translated entry at {entry['offset']} must fit "
                f"{capacity} bytes, got {len(encoded)}"
            )
        replacements.append((start, end, encoded))

    rebuilt = apply_replacements(source, replacements)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(rebuilt)
    print(f"encoded: {source_path.name} -> {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    workspace = Path(r"C:\work_han\workspace1")
    parser.add_argument("source_mec", type=Path, nargs="?")
    parser.add_argument("info_json", type=Path, nargs="?")
    parser.add_argument("lang_json", type=Path, nargs="?")
    parser.add_argument("output_mec", type=Path, nargs="?")
    parser.add_argument("--no-dosbox-x", action="store_true")
    parser.add_argument(
        "font_table", type=Path, nargs="?",
        default=Path(__file__).resolve().parent / "font_table-kor-jin-necro-compact.json",
    )
    parser.add_argument(
        "--compact-remap", "--marine-remap", dest="compact_remap", type=Path,
        default=Path(__file__).resolve().parent / "necro_compact_font_mapping_top20.json",
    )
    args = parser.parse_args()
    font_table = args.font_table
    compact_remap = args.compact_remap
    if any(value is not None for value in (args.source_mec, args.info_json, args.lang_json, args.output_mec)):
        if not all(value is not None for value in (args.source_mec, args.info_json, args.lang_json, args.output_mec)):
            parser.error("source_mec, info_json, lang_json, and output_mec must be supplied together")
        targets = [(args.source_mec, args.info_json, args.lang_json, args.output_mec)]
    else:
        targets = []
        for name in ("SYSTEM.MEC", "MAP.MEC"):
            targets.append((
                workspace / "jpn-pc98" / "MES" / name,
                workspace / "script-pc98" / "MES" / f"{name}_info.json",
                workspace / "script-pc98" / "MES" / f"{name}_lang.json",
                workspace / "kor-pc98" / "MES" / name,
            ))
    for source, info, lang, output in targets:
        encode_one(source, info, lang, output, font_table, compact_remap)
        if not args.no_dosbox_x:
            dosbox_output = workspace / "kor-pc98-dosbox-x" / "MES" / output.name
            dosbox_output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(output, dosbox_output)
            print(f"copied: {dosbox_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
