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
from pathlib import Path
from typing import Any

from gspecific.dob1.adv98_mes import decode_mes as dob1
from gspecific.adv_common.ascii import find_ascii_spans as _ascii_spans, resolve_ascii_and_gaiji


def decode_mes(data: bytes, *, structured_ascii: bool = False) -> list[dict[str, Any]]:
    base = dob1.decode_mes(data, ascii_output=structured_ascii)
    return resolve_ascii_and_gaiji(data, base)


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


def decode_document(source: Path, source_name: str, *, structured_ascii: bool = False) -> dict[str, Any]:
    data = source.read_bytes()
    tokens = decode_mes(data, structured_ascii=structured_ascii)
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


def write_decoded(input_path: Path, output_path: Path, force: bool, *, structured_ascii: bool = False) -> int:
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
        document = decode_document(source, relative.as_posix(), structured_ascii=structured_ascii)
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
    parser.add_argument("--structured-ascii", action="store_true",
                        help="parse confirmed 21 ASCII 00 output spans before lexical heuristics")
    args = parser.parse_args()
    return write_decoded(args.input, args.output, args.force, structured_ascii=args.structured_ascii)


if __name__ == "__main__":
    raise SystemExit(main())
