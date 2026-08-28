"""Find MES boundary punctuation and Japanese text/codes inside translation markers."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterator


DEFAULT_POSITIONS = {31, 61}
PUNCTUATION = {".", "!", "?"}
PUNCTUATION_MACROS = {"{.}", "{!}", "{?}"}
SPACE_CHECK_PUNCTUATION = {".", ",", "{.}", "{,}"}
JAPANESE_MARKER_PATTERN = re.compile(
    r"[ぁ-んァ-ヶ一-龯々〆ヵヶ、。・「」『』〈〉《》【】〔〕]"
)


def visible_items(value: str) -> Iterator[tuple[int, str, str]]:
    """Yield ``(1-based cell, token, kind)`` using encoder display widths."""
    value = value.replace("|", "")
    cells = 0
    index = 0
    while index < len(value):
        if value[index] == "{":
            end = value.find("}", index + 1)
            if end >= 0:
                token = value[index : end + 1]
                visible = token[1:-1]
                yield cells + 1, token, "macro"
                cells += max(1, len(visible))
                index = end + 1
                continue
        token = value[index]
        yield cells + 1, token, "literal"
        cells += 1
        index += 1


def find_hits(value: str, positions: set[int]) -> list[dict[str, object]]:
    hits = []
    for position, token, kind in visible_items(value):
        is_punctuation = (
            token in PUNCTUATION_MACROS if kind == "macro" else token in PUNCTUATION
        )
        if position in positions and is_punctuation:
            hits.append(
                {
                    "issue": "boundary_punctuation",
                    "position": position,
                    "token": token,
                    "kind": kind,
                }
            )
    return hits


def find_japanese_marker_hits(value: str) -> list[dict[str, object]]:
    hits = []
    for position, token, kind in visible_items(value):
        if kind == "macro" and JAPANESE_MARKER_PATTERN.search(token[1:-1]):
            hits.append(
                {
                    "issue": "japanese_marker",
                    "position": position,
                    "token": token,
                    "kind": kind,
                }
            )
    return hits


def find_space_after_punctuation_hits(value: str) -> list[dict[str, object]]:
    hits = []
    items = list(visible_items(value))
    for (position, token, kind), (_, next_token, next_kind) in zip(items, items[1:]):
        if (
            token in SPACE_CHECK_PUNCTUATION
            and next_kind == "literal"
            and next_token in {" ", "\t"}
        ):
            hits.append(
                {
                    "issue": "space_after_punctuation",
                    "position": position,
                    "token": token,
                    "kind": kind,
                }
            )
    return hits


def visible_cell_count(value: str) -> int:
    cells = 0
    for position, token, kind in visible_items(value):
        width = max(1, len(token[1:-1])) if kind == "macro" else 1
        cells = max(cells, position + width - 1)
    return cells


def find_display_overflow_hits(value: str, max_cells: int) -> list[dict[str, object]]:
    cells = visible_cell_count(value)
    if cells <= max_cells:
        return []
    return [
        {
            "issue": "display_overflow",
            "position": max_cells + 1,
            "token": f"{cells} cells",
            "kind": "length",
            "visible_cells": cells,
            "max_cells": max_cells,
        }
    ]


def scan_lang_file(
    path: Path, positions: set[int], max_cells: int
) -> list[dict[str, object]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for section in ("dialogue_groups", "overlay_texts"):
        for entry in document.get(section, []):
            translation = entry.get("translation")
            if not isinstance(translation, str):
                continue
            hits = find_hits(translation, positions)
            hits.extend(find_japanese_marker_hits(translation))
            hits.extend(find_space_after_punctuation_hits(translation))
            original = entry.get("original", "")
            # Some original ADV98 messages legitimately exceed three
            # 30-cell lines and continue through the engine's display flow.
            # Only flag a translated overflow when the corresponding source
            # itself fits within the configured limit.
            if not isinstance(original, str) or visible_cell_count(original) <= max_cells:
                hits.extend(find_display_overflow_hits(translation, max_cells))
            for hit in hits:
                results.append(
                    {
                        "file": path.name,
                        "section": section,
                        "id": entry.get("id")
                        or f"overlay:{entry.get('offset', '<no-offset>')}",
                        **hit,
                        "translation": translation,
                    }
                )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workspace",
        type=Path,
        nargs="?",
        default=Path(r"C:\work_han\workspace2"),
        help="workspace containing script-pc98/MES/*_lang.json",
    )
    parser.add_argument(
        "--positions",
        default="31,61",
        help="comma-separated 1-based display cells (default: 31,61)",
    )
    parser.add_argument(
        "--max-cells",
        type=int,
        default=90,
        help="maximum visible cells across three 30-cell lines (default: 90)",
    )
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args()

    positions = {int(value) for value in args.positions.split(",") if value.strip()}
    if not positions or any(position <= 0 for position in positions):
        parser.error("--positions must contain positive integers")
    if args.max_cells <= 0:
        parser.error("--max-cells must be a positive integer")

    directory = args.workspace.resolve() / "script-pc98" / "MES"
    paths = sorted(directory.glob("*_lang.json"))
    if not paths:
        parser.error(f"no *_lang.json files found: {directory}")

    results = [
        hit
        for path in paths
        for hit in scan_lang_file(path, positions, args.max_cells)
    ]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for hit in results:
            print(
                f"{hit['file']}  {hit['id']}  "
                f"issue={hit['issue']}  "
                f"cell={hit['position']}  token={hit['token']}  "
                f"section={hit['section']}"
            )
        print(f"matches: {len(results)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
