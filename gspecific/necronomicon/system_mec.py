#!/usr/bin/env python3
"""Shared helpers for Necronomicon SYSTEM.MEC menu text."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mes.adv_common.text import (
    encode_tokenized_translation,
    load_forced_dbcs_codes,
    load_font_codes,
    load_marine_remap,
)


FORMAT = "necronomicon-system-mec-lang-v1"

# SYSTEM.MEC uses the normal ADV98 compressed-hiragana representation, but its
# menu records are embedded in a script rather than in MES records.  This is
# the fixed menu labels seen in the game.
DEFAULT_TEXT_SPEC = Path(__file__).resolve().with_name("system_mec_texts.json")
FULLWIDTH_SPACE = b"\x81\x40"


def decode_adv98_bytes(raw: bytes) -> str:
    out: list[str] = []
    i = 0
    while i < len(raw):
        value = raw[i]
        if 0x2D <= value <= 0x7F:
            raw = raw  # keep the local source immutable for clarity
            pair = bytes((0x82, value + 0x72))
            try:
                out.append(pair.decode("cp932"))
            except UnicodeDecodeError:
                out.append(chr(value))
            i += 1
            continue
        if i + 1 >= len(raw):
            raise ValueError("truncated DBCS character")
        pair = raw[i : i + 2]
        out.append(pair.decode("cp932"))
        i += 2
    return "".join(out)


def load_document(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_document(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def make_info(source_path: Path, text_spec: Path = DEFAULT_TEXT_SPEC) -> dict:
    source = source_path.read_bytes()
    specification = json.loads(text_spec.read_text(encoding="utf-8"))
    if specification.get("format") != "necronomicon-system-mec-texts-v1":
        raise ValueError("unexpected SYSTEM.MEC text specification format")
    records = []
    for spec in specification.get("entries", []):
        offset = spec["offset"]
        start = int(offset, 16)
        end = int(spec["end"], 16)
        raw = source[start : end + 1]
        expected = bytes.fromhex(spec["raw_hex"])
        if raw != expected:
            raise ValueError(
                f"SYSTEM.MEC record mismatch at {offset}: "
                f"expected {expected.hex()}, got {raw.hex()}"
            )
        record = {
                "offset": offset,
                "end": spec["end"],
                "original": spec["original"],
                "raw_hex": raw.hex().upper(),
                "type": "text",
            }
        if spec.get("variable_tokens"):
            record["variable_tokens"] = spec["variable_tokens"]
        padding_mode = spec.get("padding_mode") or specification.get("padding_mode")
        if padding_mode:
            record["padding_mode"] = padding_mode
        records.append(record)
    return {
        "format": "necronomicon-system-mec-info-v1",
        "source_name": source_path.name,
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "records": records,
    }


def encode_menu_text(
    text: str,
    font_table: Path,
    compact_remap: Path,
) -> bytes:
    """Encode MEC menu text; ``_`` is an explicit ``81 40`` space token."""
    codes = load_font_codes(font_table)
    forced_dbcs_codes = load_forced_dbcs_codes(font_table)
    remap = load_marine_remap(compact_remap)
    return encode_tokenized_translation(
        text,
        codes,
        forced_dbcs_codes=forced_dbcs_codes,
        one_byte_codes=remap,
    )
