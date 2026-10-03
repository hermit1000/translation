#!/usr/bin/env python3
"""Build a reusable translation dictionary from Necronomicon MES JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


FORMAT = "necronomicon-adv98-mes-lang-v1"
SECTIONS = ("dialogue_groups", "overlay_texts")


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_pair(dictionary: dict, original: object, translation: object, reference: str) -> None:
    if not isinstance(original, str) or not original.strip() or not isinstance(translation, str):
        return
    entry = dictionary.setdefault(original, {"count": 0, "reference": 0, "translated": [], "references": []})
    entry["reference"] += 1
    entry["references"].append(reference)
    if translation not in entry["translated"]:
        entry["translated"].append(translation)
        entry["count"] = len(entry["translated"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=Path(r"C:\work_han\workspace1"))
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    # Dialogue dictionaries are only for MES resources.  SYSTEM.MEC has a
    # different lang format even though it lives in the same directory.
    paths = sorted((workspace / "script-pc98" / "MES").glob("*.MES_lang.json"))
    if not paths:
        parser.error(f"no *_lang.json files found: {workspace / 'script-pc98' / 'MES'}")
    dictionary: dict = {}
    entries = translated = skipped = 0
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("format") != FORMAT:
            # SYSTEM.MEC and other Necronomicon resources use their own
            # lang formats and are handled by dedicated tools.  They share
            # the MES directory, so skip them here instead of aborting the
            # dialogue-dictionary build.
            skipped += 1
            continue
        for section in SECTIONS:
            for entry in document.get(section, []):
                if not isinstance(entry, dict):
                    continue
                entries += 1
                if isinstance(entry.get("translation"), str) and entry["translation"].strip():
                    translated += 1
                add_pair(dictionary, entry.get("original"), entry.get("translation"), f"{path.name}:{entry.get('id', '')}")
    annoying = {key: {"translated": value["translated"]} for key, value in dictionary.items() if value["count"] > 1}
    write_json(workspace / "dictionary.json", dictionary)
    write_json(workspace / "annoying.json", annoying)
    percent = translated / entries * 100 if entries else 100.0
    print(f"MES files: {len(paths)}, entries: {entries}")
    if skipped:
        print(f"Non-MES lang files skipped: {skipped}")
    print(f"Translation progress: {translated}/{entries} ({percent:.2f}%)")
    print(f"dictionary.json: {len(dictionary)} source keys")
    print(f"annoying.json: {len(annoying)} ambiguous source keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
