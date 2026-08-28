#!/usr/bin/env python3
"""Decode Dead of the Brain 2 ADV98 MES files.

DOB2 retains DOB1's compressed-hiragana byte range, but also stores genuine
ASCII messages in that same range.  This decoder recognizes clearly delimited
English strings before applying the DOB1 lexical interpretation.  Undefined
CP932 ``EBxx`` pairs are retained as DOB2 gaiji tokens instead of replacement
characters.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from gspecific.dob1.adv98_mes import decode_mes as dob1


def _ascii_spans(data: bytes) -> dict[int, int]:
    """Return conservative, clearly English byte spans as start -> end."""
    spans: dict[int, int] = {}
    # 0x21 is ADV98's non-printing ASCII-output marker in DOB2.  Excluding it
    # keeps strings such as ``!Please ...`` aligned with the actual screen,
    # where the leading exclamation mark is not drawn.
    for match in re.finditer(rb"[\x20\x22-\x7e]{2,}", data):
        start, end = match.span()
        raw = match.group()
        stripped = raw.lstrip()
        # Quoted graphics commands and ``se "..."`` audio commands are
        # ADV98 operands, not screen text.  Leave them to the base lexer.
        if stripped.startswith(b'"') or stripped.lower().startswith(b'se "'):
            continue
        letters = bytes(value for value in raw if 0x41 <= value <= 0x5A or 0x61 <= value <= 0x7A)
        if len(letters) < 2:
            continue
        has_space = b" " in raw
        uppercase_label = letters == letters.upper()
        nul_terminated = end < len(data) and data[end] == 0
        a5_delimited = (
            start > 0
            and end < len(data)
            and data[start - 1] == 0xA5
            and data[end] == 0xA5
        )
        # Mixed-case text is accepted only when spacing or a NUL terminator
        # makes it unmistakably ASCII.  This avoids converting ordinary DOB2
        # compressed hiragana which happens to occupy printable ASCII bytes.
        if has_space or nul_terminated or (uppercase_label and a5_delimited):
            spans[start] = end
    return spans


def decode_mes(data: bytes) -> list[dict[str, Any]]:
    base = dob1.decode_mes(data)
    token_starts = {token["offset"] for token in base}
    token_ends = {token["offset"] + token["size"] for token in base}
    ascii_spans: dict[int, int] = {}
    for raw_start, raw_end in _ascii_spans(data).items():
        # A printable SJIS trail byte can attach itself to the front of an
        # English regex match.  Trim at most that one byte to a token boundary.
        starts = [value for value in (raw_start, raw_start + 1) if value in token_starts]
        ends = [value for value in (raw_end, raw_end - 1) if value in token_ends]
        if starts and ends and min(starts) < max(ends):
            ascii_spans[min(starts)] = max(ends)
    result: list[dict[str, Any]] = []
    index = 0

    while index < len(base):
        token = base[index]
        start = token["offset"]
        ascii_end = ascii_spans.get(start)
        if ascii_end is not None:
            result.append(
                dob1.make_token(
                    start,
                    ascii_end - start,
                    data[start:ascii_end],
                    "text",
                    data[start:ascii_end].decode("ascii"),
                    encoding="ascii",
                    display_text=start > 0 and data[start - 1] == 0x21,
                )
            )
            while index < len(base) and base[index]["offset"] < ascii_end:
                index += 1
            continue

        raw = token["bytes"]
        if token["type"] == "text" and len(raw) == 2 and "\ufffd" in str(token["value"]):
            result.append(
                dob1.make_token(
                    start,
                    2,
                    bytes(raw),
                    "gaiji",
                    f"GAIJI_{raw[0]:02X}{raw[1]:02X}",
                )
            )
        else:
            result.append(token)
        index += 1

    dob1.verify_tokens(data, result)
    return result


def make_records(tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = dob1.make_readable_records(tokens)
    display_offsets = {
        f'{token["offset"]:05X}' for token in tokens if token.get("display_text")
    }
    for record in records:
        if record["type"] == "text":
            record["original"] = record.pop("text")
            if record["offset"] in display_offsets:
                record["translation_candidate"] = True
        elif record["type"] == "gaiji":
            record["editable"] = False
    return records


def decode_document(source: Path, source_name: str) -> dict[str, Any]:
    data = source.read_bytes()
    tokens = decode_mes(data)
    records = make_records(tokens)
    candidates = [
        record
        for record in records
        if record["type"] == "text"
        and record["translation_candidate"]
        and record["original"].strip()
    ]
    return {
        "format": "dob2-adv98-mes-jpn-v1",
        "language": "jpn",
        "source": source_name,
        "source_size": len(data),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "warning": "Provisional DOB2 lexical decode; review candidates before reinsertion.",
        "text_record_count": sum(record["type"] == "text" for record in records),
        "translation_candidate_count": len(candidates),
        "gaiji_count": sum(record["type"] == "gaiji" for record in records),
        "records": records,
    }


def write_decoded(input_path: Path, output_path: Path, force: bool) -> int:
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    if input_path.is_file():
        sources = [(input_path, Path(input_path.name))]
    else:
        sources = [
            (path, path.relative_to(input_path))
            for path in sorted(input_path.rglob("*"))
            if path.is_file() and path.suffix.upper() == ".MES"
        ]
    if not sources:
        raise ValueError(f"no MES files found: {input_path}")

    totals = {"files_written": 0, "text_records": 0, "translation_candidates": 0, "gaiji": 0}
    for source, relative in sources:
        destination = (
            output_path
            if input_path.is_file() and output_path.suffix.lower() == ".json"
            else output_path / relative.parent / f"{relative.name}_jpn.json"
        )
        if destination.exists() and not force:
            raise FileExistsError(f"output exists; pass --force: {destination}")
        document = decode_document(source, relative.as_posix())
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        totals["files_written"] += 1
        totals["text_records"] += document["text_record_count"]
        totals["translation_candidates"] += document["translation_candidate_count"]
        totals["gaiji"] += document["gaiji_count"]
    print(json.dumps(totals, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    return write_decoded(args.input, args.output, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
