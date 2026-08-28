"""Extract MES text records missing from dialogue and overlay translation lists."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


DISPLAY_TEXT_PATTERN = re.compile(r"[一-龯ァ-ヶＡ-Ｚ]")
TEXT_JOIN_SLOTS = {"0D", "0E", "0F", "10", "11", "12"}


def default_workspace() -> Path:
    current = Path.cwd()
    if (current / "script-pc98" / "MES").is_dir():
        return current
    return Path(r"C:\work_han\workspace2")


def is_slot(record: object, slot: str) -> bool:
    return (
        isinstance(record, dict)
        and record.get("type") == "command"
        and record.get("macro_slot") == slot
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=default_workspace())
    parser.add_argument(
        "--output",
        type=Path,
        help="output JSON (default: <workspace>/untracked_mes_text_candidates.json)",
    )
    parser.add_argument(
        "--originals-output",
        type=Path,
        help="unique originals JSON (default: <workspace>/untracked_mes_text_originals.json)",
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_dir = workspace / "jpn-pc98" / "MES"
    mes_dir = workspace / "script-pc98" / "MES"
    output = (args.output or workspace / "untracked_mes_text_candidates.json").resolve()
    originals_output = (
        args.originals_output or workspace / "untracked_mes_text_originals.json"
    ).resolve()

    source_names = {path.name for path in source_dir.glob("*.MES")}
    info_names = {
        path.name.removesuffix("_info.json") for path in mes_dir.glob("*_info.json")
    }
    lang_names = {
        path.name.removesuffix("_lang.json") for path in mes_dir.glob("*_lang.json")
    }

    occurrences: dict[str, list[dict[str, object]]] = defaultdict(list)
    for info_path in sorted(mes_dir.glob("*_info.json")):
        stem = info_path.name.removesuffix("_info.json")
        lang_path = mes_dir / f"{stem}_lang.json"
        if not lang_path.is_file():
            continue
        info = json.loads(info_path.read_text(encoding="utf-8"))
        lang = json.loads(lang_path.read_text(encoding="utf-8"))

        tracked = {
            segment.get("offset")
            for dialogue in info.get("dialogues", [])
            if isinstance(dialogue, dict)
            for segment in dialogue.get("segments", [])
            if isinstance(segment, dict) and segment.get("offset")
        }
        tracked.update(
            overlay.get("offset")
            for overlay in lang.get("overlay_texts", [])
            if isinstance(overlay, dict) and overlay.get("offset")
        )

        records = info.get("records", [])
        # A displayed sentence can be split into several text records by
        # punctuation commands.  Older extraction sometimes tracked only the
        # first record.  Expand from every tracked text through those joins so
        # all continuation records become candidates as well.
        connected = set(tracked)
        changed = True
        while changed:
            changed = False
            for index, record in enumerate(records):
                if not isinstance(record, dict) or record.get("type") != "text":
                    continue
                offset = record.get("offset")
                if offset in connected:
                    continue
                neighbours = []
                if index >= 2 and is_slot(records[index - 1], records[index - 1].get("macro_slot")):
                    if records[index - 1].get("macro_slot") in TEXT_JOIN_SLOTS:
                        neighbours.append(records[index - 2])
                if index + 2 < len(records) and is_slot(records[index + 1], records[index + 1].get("macro_slot")):
                    if records[index + 1].get("macro_slot") in TEXT_JOIN_SLOTS:
                        neighbours.append(records[index + 2])
                if any(
                    isinstance(neighbour, dict)
                    and neighbour.get("type") == "text"
                    and neighbour.get("offset") in connected
                    for neighbour in neighbours
                ):
                    connected.add(offset)
                    changed = True

        for index, record in enumerate(records):
            if not isinstance(record, dict) or record.get("type") != "text":
                continue
            if record.get("offset") in tracked:
                continue
            previous = records[index - 1] if index else None
            following = records[index + 1] if index + 1 < len(records) else None
            adjacent_slot_03 = is_slot(previous, "03") or is_slot(following, "03")
            tracked_continuation = record.get("offset") in connected
            if not adjacent_slot_03 and not tracked_continuation:
                continue

            original = record.get("original")
            if not isinstance(original, str) or not original:
                continue
            compact = original.strip()
            looks_like_display_text = bool(
                DISPLAY_TEXT_PATTERN.search(original)
                or compact.startswith(("〔", "《", "「", "『", "（"))
            )
            if tracked_continuation and not looks_like_display_text:
                continue
            confidence = (
                "high"
                if tracked_continuation
                or (len(compact) >= 4 and DISPLAY_TEXT_PATTERN.search(original))
                else "review"
            )
            occurrences[original].append(
                {
                    "file": stem,
                    "offset": record.get("offset"),
                    "end": record.get("end"),
                    "confidence": confidence,
                    "previous_macro_slot": previous.get("macro_slot")
                    if isinstance(previous, dict)
                    else None,
                    "next_macro_slot": following.get("macro_slot")
                    if isinstance(following, dict)
                    else None,
                    "tracked_continuation": tracked_continuation,
                }
            )

    candidates = []
    for original, items in occurrences.items():
        confidence = "high" if any(item["confidence"] == "high" for item in items) else "review"
        candidates.append(
            {
                "original": original,
                "confidence": confidence,
                "occurrence_count": len(items),
                "occurrences": items,
            }
        )
    candidates.sort(
        key=lambda item: (
            0 if item["confidence"] == "high" else 1,
            item["occurrences"][0]["file"],
            item["occurrences"][0]["offset"],
        )
    )

    high = [item for item in candidates if item["confidence"] == "high"]
    report = {
        "format": "dob1-untracked-mes-text-candidates-v1",
        "workspace": str(workspace),
        "rule": "untracked text record immediately adjacent to CALL_BUILTIN slot 03",
        "summary": {
            "source_mes_files": len(source_names),
            "info_files": len(info_names),
            "lang_files": len(lang_names),
            "source_without_info": sorted(source_names - info_names),
            "source_without_lang": sorted(source_names - lang_names),
            "candidate_records": sum(item["occurrence_count"] for item in candidates),
            "unique_candidates": len(candidates),
            "high_confidence_records": sum(item["occurrence_count"] for item in high),
            "high_confidence_unique": len(high),
        },
        "candidates": candidates,
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    originals_report = {
        "high_confidence_originals": [
            item["original"] for item in candidates if item["confidence"] == "high"
        ],
        "review_originals": [
            item["original"] for item in candidates if item["confidence"] == "review"
        ],
    }
    originals_output.write_text(
        json.dumps(originals_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"output: {output}")
    print(f"originals output: {originals_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
