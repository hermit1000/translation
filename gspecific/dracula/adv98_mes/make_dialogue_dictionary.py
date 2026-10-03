#!/usr/bin/env python3
"""Build a reusable dictionary from Dracula MES language JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SECTIONS = ("dialogue_groups", "overlay_texts")
FORMAT = "dracula-adv98-mes-lang-v1"


def write_json(path: Path, value: dict) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text.replace("\n", "\r\n"), encoding="utf-8", newline="")


def add_pair(dictionary: dict, original: object, translation: object, reference: str) -> None:
    if not isinstance(original, str) or not original.strip():
        return
    if not isinstance(translation, str):
        return
    entry = dictionary.setdefault(
        original,
        {"count": 0, "reference": 0, "translated": [], "references": []},
    )
    entry["reference"] += 1
    entry["references"].append(reference)
    if translation not in entry["translated"]:
        entry["translated"].append(translation)
        entry["count"] = len(entry["translated"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=Path(r"C:\work_han\workspace2"))
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    mes_dir = workspace / "script-pc98" / "MES"
    paths = sorted(mes_dir.glob("*_lang.json"))
    if not paths:
        parser.error(f"no *_lang.json files found: {mes_dir}")

    dictionary: dict = {}
    entries = translated = 0
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("format") != FORMAT:
            parser.error(f"unexpected format: {path}")
        for section in SECTIONS:
            for item in document.get(section, []):
                if not isinstance(item, dict):
                    continue
                entries += 1
                value = item.get("translation")
                if isinstance(value, str) and value.strip():
                    translated += 1
                add_pair(dictionary, item.get("original"), value, f"{path.name}:{item.get('id', '')}")

    annoying = {
        key: {"translated": value["translated"]}
        for key, value in dictionary.items()
        if value["count"] > 1
    }
    write_json(workspace / "dictionary.json", dictionary)
    write_json(workspace / "annoying.json", annoying)
    percent = translated / entries * 100 if entries else 100.0
    print(f"MES files: {len(paths)}, entries: {entries}")
    print(f"Translation progress: {translated}/{entries} ({percent:.2f}%)")
    print(f"dictionary.json: {len(dictionary)} source keys")
    print(f"annoying.json: {len(annoying)} ambiguous source keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
