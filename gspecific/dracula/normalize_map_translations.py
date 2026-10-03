#!/usr/bin/env python3
"""Apply Dracula MES punctuation spacing rules to MAP translation JSON files."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(r"C:\work_han\workspace2\script-pc98\MES")
    for path in sorted(root.glob("MAP*.MES_lang.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for entry in [*data.get("dialogue_groups", []), *data.get("overlay_texts", [])]:
            value = entry.get("translation")
            if not isinstance(value, str):
                continue
            normalized = value.replace(". ", ".").replace(", ", ",")
            if normalized != value:
                entry["translation"] = normalized
                changed = True
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"updated: {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
