"""Build a reusable translation dictionary from DOB2 MES language JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SECTIONS = ("dialogue_groups", "overlay_texts")


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
    parser.add_argument("workspace", type=Path, nargs="?", default=Path(r"C:\work_han\workspace1"))
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    mes_dir = workspace / "script-pc98" / "MES"
    paths = sorted(mes_dir.glob("*_lang.json"))
    if not paths:
        parser.error(f"no *_lang.json files found: {mes_dir}")

    dictionary: dict = {}
    entries = 0
    translated = 0
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        for section in SECTIONS:
            for entry in document.get(section, []):
                if not isinstance(entry, dict):
                    continue
                entries += 1
                value = entry.get("translation")
                if isinstance(value, str) and value.strip():
                    translated += 1
                add_pair(dictionary, entry.get("original"), value, f"{path.name}:{entry.get('id', '')}")

    annoying = {
        key: {"translated": value["translated"]}
        for key, value in dictionary.items()
        if value["count"] > 1
    }
    for name, payload in (("dictionary.json", dictionary), ("annoying.json", annoying)):
        (workspace / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    percent = translated / entries * 100 if entries else 100.0
    print(f"MES files: {len(paths)}, entries: {entries}")
    print(f"Translation progress: {translated}/{entries} ({percent:.2f}%)")
    print(f"dictionary.json: {len(dictionary)} source keys")
    print(f"annoying.json: {len(annoying)} ambiguous source keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
