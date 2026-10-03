#!/usr/bin/env python3
"""Create DOB2 MES info/lang JSON files for translation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .decode_mes import decode_document
from mes.tools.migrate_ascii import prepare_migration


SPEAKER_RE = re.compile(r"^［([^］]+)］")


def make_lang(info_name: str, document: dict) -> dict:
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
        "format": "dob2-adv98-mes-lang-v1",
        "source_info": info_name,
        "dialogue_groups": dialogues,
        "overlay_texts": overlays,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workspace",
        type=Path,
        nargs="?",
        default=Path(r"C:\work_han\workspace1"),
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output-dir", type=Path, help="write fresh JSON to a separate directory")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_dir = workspace / "jpn-pc98" / "MES"
    output_dir = args.output_dir or workspace / "script-pc98" / "MES"
    sources = sorted(source_dir.glob("*.MES"))
    if not sources:
        raise ValueError(f"no MES files found: {source_dir}")

    written = 0
    entries = 0
    planned = []
    for source in sources:
        info_path = output_dir / f"{source.name}_info.json"
        lang_path = output_dir / f"{source.name}_lang.json"
        if not args.force and (info_path.exists() or lang_path.exists()):
            raise FileExistsError(f"output exists; pass --force: {info_path} / {lang_path}")
        document = decode_document(source, f"MES/{source.name}")
        document["format"] = "dob2-adv98-mes-info-v1"
        lang = make_lang(info_path.name, document)
        if args.force and (info_path.exists() or lang_path.exists()):
            if not (info_path.exists() and lang_path.exists()):
                raise ValueError(f"both existing info/lang files are required: {source.name}")
            previous_info = json.loads(info_path.read_text(encoding="utf-8"))
            previous = json.loads(lang_path.read_text(encoding="utf-8"))
            if previous.get("source_info") != info_path.name:
                raise ValueError(f"source info reference mismatch: {source.name}")
            document, lang, report = prepare_migration(source.read_bytes(), previous_info, previous, document)
            if not report["safe_to_write"]:
                raise ValueError(f"{source.name}: changed translation ranges require review; use mes.tools.migrate_ascii")
        planned.append((info_path, lang_path, document, lang))
    # Validate every existing pair before overwriting any file in this batch.
    output_dir.mkdir(parents=True, exist_ok=True)
    for info_path, lang_path, document, lang in planned:
        info_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lang_path.write_text(json.dumps(lang, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written += 1
        entries += len(lang["dialogue_groups"]) + len(lang["overlay_texts"])

    print(json.dumps({"files_written": written, "translation_entries": entries}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
