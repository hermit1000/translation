"""Build a reusable dictionary from Marine Philt MES language JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SECTIONS = ("dialogue_groups", "overlay_texts")
FORMAT = "marine-philt-adv98-mes-lang-v1"


def write_json(path: Path, value: dict) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text.replace("\n", "\r\n"), encoding="utf-8", newline="")


def source_text(item: dict) -> str | None:
    """Return the dictionary key for a Marine dialogue item.

    Connected dialogue is edited as one root entry.  Its combined source is
    therefore the reusable key; ordinary entries continue to use ``original``.
    """
    combined = item.get("combined_original")
    if isinstance(combined, str) and combined.strip():
        return combined
    original = item.get("original")
    return original if isinstance(original, str) else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=Path(r"C:\work_han\workspace4"))
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    paths = sorted((workspace / "script-pc98" / "MES").glob("*_lang.json"))
    if not paths:
        parser.error("no MES language JSON files found")

    dictionary: dict = {}
    entries = translated = 0
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("format") != FORMAT:
            parser.error(f"unexpected format: {path}")
        for section in SECTIONS:
            for item in document.get(section, []):
                entries += 1
                value = item.get("translation")
                if not isinstance(value, str):
                    continue
                if value.strip():
                    translated += 1
                else:
                    # Normalize untranslated entries for the reusable
                    # dictionary.  This prevents the same source from being
                    # represented by both "" and "@keep".
                    value = "@keep"
                original = source_text(item)
                if not isinstance(original, str) or not original.strip():
                    continue
                record = dictionary.setdefault(
                    original, {"count": 0, "reference": 0, "translated": [], "references": []}
                )
                record["reference"] += 1
                record["references"].append(f"{path.name}:{item.get('id', '')}")
                if value not in record["translated"]:
                    record["translated"].append(value)
                    record["count"] = len(record["translated"])

    annoying = {key: {"translated": value["translated"]} for key, value in dictionary.items() if value["count"] > 1}
    write_json(workspace / "dictionary.json", dictionary)
    write_json(workspace / "annoying.json", annoying)
    percent = translated / entries * 100 if entries else 100.0
    print(f"MES files: {len(paths)}, entries: {entries}")
    print(f"Translation progress: {translated}/{entries} ({percent:.2f}%)")
    print(f"dictionary.json: {len(dictionary)}; annoying.json: {len(annoying)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

