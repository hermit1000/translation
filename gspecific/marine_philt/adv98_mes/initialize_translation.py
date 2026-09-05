#!/usr/bin/env python3
"""Create Marine Philt MES info/lang JSON files for translation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .decode_mes import decode_document


SPEAKER_RE = re.compile(r"^(?:se [^［]*?)?［([^］]+)］")


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
        "format": "marine-philt-adv98-mes-lang-v1",
        "source_info": info_name,
        "dialogue_groups": dialogues,
        "overlay_texts": overlays,
    }


def _write_json(path: Path, value: dict) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text.replace("\n", "\r\n"), encoding="utf-8", newline="")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_dir = workspace / "jpn-pc98" / "MES"
    output_dir = workspace / "script-pc98" / "MES"
    sources = sorted(source_dir.glob("*.MES"))
    if not sources:
        raise ValueError(f"no MES files found: {source_dir}")

    written = 0
    entries = 0
    for source in sources:
        info_path = output_dir / f"{source.name}_info.json"
        lang_path = output_dir / f"{source.name}_lang.json"
        if not args.force and (info_path.exists() or lang_path.exists()):
            raise FileExistsError(f"output exists; pass --force: {info_path} / {lang_path}")
        document = decode_document(source, f"MES/{source.name}")
        lang = make_lang(info_path.name, document)
        if args.force and lang_path.exists():
            previous = json.loads(lang_path.read_text(encoding="utf-8"))
            previous_by_offset = {
                entry.get("offset"): entry
                for section in ("dialogue_groups", "overlay_texts")
                for entry in previous.get(section, [])
            }
            for section in ("dialogue_groups", "overlay_texts"):
                for entry in lang[section]:
                    old = previous_by_offset.get(entry["offset"])
                    if old and old.get("original") == entry["original"]:
                        entry["translation"] = old.get("translation", "")
                        entry["status"] = old.get("status", entry["status"])
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_json(info_path, document)
        _write_json(lang_path, lang)
        written += 2
        entries += len(lang["dialogue_groups"]) + len(lang["overlay_texts"])

    print(json.dumps({"json_files_written": written, "mes_files": len(sources), "translation_entries": entries}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

