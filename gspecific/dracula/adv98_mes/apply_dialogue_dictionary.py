#!/usr/bin/env python3
"""Apply unambiguous dictionary translations to Dracula MES language JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .make_dialogue_dictionary import FORMAT, SECTIONS, write_json
except ImportError:  # Support direct execution: python apply_dialogue_dictionary.py
    from make_dialogue_dictionary import FORMAT, SECTIONS, write_json


def load_candidates(path: Path) -> dict[str, str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    candidates = {}
    for original, entry in document.items():
        if not isinstance(original, str) or not isinstance(entry, dict):
            continue
        translations = entry.get("translated")
        if not isinstance(translations, list):
            continue
        unique = list(dict.fromkeys(value for value in translations if isinstance(value, str)))
        if len(unique) == 1 and unique[0].strip():
            candidates[original] = unique[0]
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=Path(r"C:\work_han\workspace2"))
    parser.add_argument("--dictionary", type=Path, help="dictionary JSON path (default: workspace/annoying.json)")
    parser.add_argument("--only-empty", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    dictionary_path = (args.dictionary or workspace / "annoying.json").resolve()
    mes_dir = workspace / "script-pc98" / "MES"
    if not dictionary_path.is_file():
        parser.error(f"dictionary not found: {dictionary_path}")
    paths = sorted(mes_dir.glob("*_lang.json"))
    if not paths:
        parser.error(f"no *_lang.json files found: {mes_dir}")

    candidates = load_candidates(dictionary_path)
    changed_files = changed_entries = 0
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("format") != FORMAT:
            parser.error(f"unexpected format: {path}")
        file_changes = 0
        for section in SECTIONS:
            for entry in document.get(section, []):
                if not isinstance(entry, dict):
                    continue
                candidate = candidates.get(entry.get("original"))
                current = entry.get("translation")
                if candidate is None or current == candidate:
                    continue
                if args.only_empty and isinstance(current, str) and current.strip():
                    continue
                entry["translation"] = candidate
                entry["status"] = "passed" if candidate == "@keep" else "pending"
                file_changes += 1
        if not file_changes:
            continue
        changed_files += 1
        changed_entries += file_changes
        print(f"{path.name}: {file_changes}")
        if not args.dry_run:
            write_json(path, document)

    mode = "preview" if args.dry_run else "written"
    print(
        f"{mode}: {changed_entries} entries in {changed_files} files; "
        f"applicable entries: {len(candidates)}; source: {dictionary_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
