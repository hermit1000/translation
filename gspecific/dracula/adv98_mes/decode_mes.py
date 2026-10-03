#!/usr/bin/env python3
"""Decode Dracula ADV98 MES files into structured Japanese JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from gspecific.dob2.adv98_mes.decode_mes import (
    decode_mes as decode_tokens,
    make_records,
)


SPEAKER_RE = re.compile(r"^［([^］]+)］")


def decode_document(source: Path, source_name: str, *, structured_ascii: bool = True) -> dict[str, Any]:
    """Decode one Dracula MES file while preserving source metadata."""
    data = source.read_bytes()
    tokens = decode_tokens(data, structured_ascii=structured_ascii)
    records = make_records(tokens)
    candidates = [
        record
        for record in records
        if record["type"] == "text"
        and record.get("translation_candidate")
        and record["original"].strip()
    ]
    return {
        "format": "dracula-adv98-mes-jpn-v1",
        "language": "jpn",
        "source": source_name,
        "source_size": len(data),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "structured_ascii": structured_ascii,
        "warning": "Provisional Dracula lexical decode; review candidates before reinsertion.",
        "text_record_count": sum(record["type"] == "text" for record in records),
        "translation_candidate_count": len(candidates),
        "gaiji_count": sum(record["type"] == "gaiji" for record in records),
        "records": records,
    }


def make_lang(info_name: str, document: dict[str, Any]) -> dict[str, Any]:
    dialogues = []
    overlays = []
    for record in document["records"]:
        if (
            record.get("type") != "text"
            or not record.get("translation_candidate")
            or not record.get("original", "").strip()
        ):
            continue
        dialogue = SPEAKER_RE.match(record["original"]) is not None
        entry = {
            "id": f'{"dialogue" if dialogue else "overlay"}:{record["offset"]}',
            "offset": record["offset"],
            "original": record["original"],
            "translation": "",
            "status": "incomplete: untranslated dialogue" if dialogue else "incomplete: untranslated overlay",
        }
        (dialogues if dialogue else overlays).append(entry)
    return {
        "format": "dracula-adv98-mes-lang-v1",
        "source_info": info_name,
        "dialogue_groups": dialogues,
        "overlay_texts": overlays,
    }


def write_decoded(input_path: Path, output_path: Path, force: bool, *, structured_ascii: bool = True) -> int:
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

    totals = {
        "files_written": 0,
        "translation_entries": 0,
        "text_records": 0,
        "translation_candidates": 0,
        "gaiji": 0,
    }
    for source, relative in sources:
        document = decode_document(source, relative.as_posix(), structured_ascii=structured_ascii)
        document["format"] = "dracula-adv98-mes-info-v1"
        info_path = output_path / relative.parent / f"{relative.name}_info.json"
        lang_path = output_path / relative.parent / f"{relative.name}_lang.json"
        if not force and (info_path.exists() or lang_path.exists()):
            raise FileExistsError(f"output exists; pass --force: {info_path} / {lang_path}")
        lang = make_lang(info_path.name, document)
        info_path.parent.mkdir(parents=True, exist_ok=True)
        info_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lang_path.write_text(json.dumps(lang, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        totals["files_written"] += 1
        totals["translation_entries"] += len(lang["dialogue_groups"]) + len(lang["overlay_texts"])
        totals["text_records"] += document["text_record_count"]
        totals["translation_candidates"] += document["translation_candidate_count"]
        totals["gaiji"] += document["gaiji_count"]
    print(json.dumps(totals, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=Path(r"C:\work_han\workspace2\jpn-pc98\MES"),
        help="Dracula MES file or directory",
    )
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=Path(r"C:\work_han\workspace2\script-pc98\MES"),
        help="directory for *_info.json and *_lang.json output",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--structured-ascii",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="parse confirmed 21 ASCII 00 output spans before lexical heuristics",
    )
    args = parser.parse_args()
    return write_decoded(args.input, args.output, args.force, structured_ascii=args.structured_ascii)


if __name__ == "__main__":
    raise SystemExit(main())
