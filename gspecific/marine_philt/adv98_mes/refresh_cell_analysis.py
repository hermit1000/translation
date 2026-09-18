#!/usr/bin/env python3
"""Refresh stored Marine Philt translation cell analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


NEXT_MARKER = "{next}"
DEFAULT_LIMIT = 77
FULL_LIMIT = 81


def refresh(document: dict, limit: int = DEFAULT_LIMIT) -> int:
    updated = 0
    for section in ("dialogue_groups", "overlay_texts"):
        for entry in document.get(section, []):
            translation = entry.get("translation")
            if not isinstance(translation, str) or not translation or translation == "@keep":
                entry.pop("cell_analysis", None)
                continue
            parts = translation.split(NEXT_MARKER)
            entry_limit = FULL_LIMIT if parts[0].lstrip().startswith(("[", "〔")) else limit
            analysis = []
            for index, part in enumerate(parts, 1):
                cells = len(part)
                remaining = entry_limit - cells
                analysis.append({
                    "segment": index,
                    "cells": cells,
                    "limit": entry_limit,
                    "remaining": remaining,
                    "status": "OVER" if remaining < 0 else "FULL" if remaining == 0 else "OK",
                })
            entry["cell_analysis"] = analysis
            updated += 1
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lang_json", type=Path)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()
    document = json.loads(args.lang_json.read_text(encoding="utf-8"))
    updated = refresh(document, args.limit)
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    args.lang_json.write_text(text.replace("\n", "\r\n"), encoding="utf-8", newline="")
    print(json.dumps({"updated_entries": updated, "limit": args.limit}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
