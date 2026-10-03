#!/usr/bin/env python3
"""Annotate Necronomicon MES language JSON with display-line relationships."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FORMAT = "necronomicon-adv98-mes-lang-v1"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_a5(record: dict[str, Any]) -> bool:
    return record.get("type") == "control" and record.get("raw_hex", "").replace(" ", "").upper() == "A5"


def is_display_continuation_control(record: dict[str, Any]) -> bool:
    """Return whether a control keeps the next text on the same dialogue display."""
    return is_a5(record) or record.get("name") == "CMD_A7"


def leading_cells(text: str) -> int:
    count = 0
    for character in text:
        if character in (" ", "\u3000"):
            count += 1
        else:
            break
    return count


def speaker_info(text: str) -> tuple[str | None, int | None]:
    if not text.startswith("「"):
        return None, None
    closing = text.find("」")
    if closing < 0:
        return None, None
    speaker = text[: closing + 1]
    content_start = closing + 1
    while content_start < len(text) and text[content_start] in (" ", "\u3000"):
        content_start += 1
    return speaker, content_start


def build_groups(info: dict[str, Any], lang: dict[str, Any]) -> list[dict[str, Any]]:
    entries = {
        entry.get("offset"): entry
        for section in ("dialogue_groups", "overlay_texts")
        for entry in lang.get(section, [])
        if isinstance(entry, dict) and entry.get("offset")
    }
    records = info.get("records", [])
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    previous_was_continuation_control = False

    for record in records:
        if record.get("type") == "control" or record.get("name") == "CMD_A7":
            previous_was_continuation_control = is_display_continuation_control(record)
            continue
        if record.get("type") != "text":
            previous_was_continuation_control = False
            continue

        offset = record.get("offset")
        entry = entries.get(offset)
        if entry is None:
            previous_was_continuation_control = False
            continue

        original = entry.get("original", "")
        speaker, speaker_content_start = speaker_info(original)
        continuation = current is not None and previous_was_continuation_control
        if not continuation:
            current = {
                "id": f"display:{offset}",
                "start_offset": offset,
                "end_offset": offset,
                "speaker": speaker,
                "speaker_offset": offset if speaker else None,
                "lines": [],
            }
            groups.append(current)

        assert current is not None
        line = {
            "offset": offset,
            "role": "continuation" if continuation else ("speaker" if speaker else "text"),
            "line_index": len(current["lines"]),
            "leading_cells": leading_cells(original),
        }
        if speaker is not None:
            line["speaker"] = speaker
            line["speaker_content_start_cells"] = speaker_content_start
        current["lines"].append(line)
        current["end_offset"] = record.get("end", offset)
        previous_was_continuation_control = False

    for group in groups:
        group["line_count"] = len(group["lines"])
        group["has_continuation"] = len(group["lines"]) > 1
        for line in group["lines"]:
            entry = entries.get(line["offset"])
            if entry is None:
                continue
            entry["display_group"] = group["id"]
            entry["display_role"] = line["role"]
            entry["display_line_index"] = line["line_index"]
            entry["display_leading_cells"] = line["leading_cells"]
            if group.get("speaker"):
                entry["display_speaker"] = group["speaker"]
            if "speaker_content_start_cells" in line:
                entry["display_speaker_content_start_cells"] = line["speaker_content_start_cells"]
    return groups


def annotate_translated_layout(groups: list[dict[str, Any]], lang: dict[str, Any]) -> None:
    """Persist translated speaker columns and continuation columns."""
    entries = {
        entry.get("offset"): entry
        for section in ("dialogue_groups", "overlay_texts")
        for entry in lang.get(section, [])
        if isinstance(entry, dict) and entry.get("offset")
    }
    for group in groups:
        speaker_entry = entries.get(group.get("speaker_offset"))
        if not speaker_entry:
            continue
        translated = speaker_entry.get("translation")
        if not isinstance(translated, str):
            continue
        speaker, content_start = speaker_info(translated)
        if speaker is None or content_start is None:
            continue
        stored_column = speaker_entry.get("display_translation_content_start_cells_strict")
        if not isinstance(stored_column, int) or stored_column < 0:
            stored_column = group.get("display_translation_content_start_cells_strict")
        if isinstance(stored_column, int) and stored_column >= 0:
            content_start = stored_column
        speaker_entry["display_translation_speaker"] = speaker
        group["display_translation_speaker"] = speaker
        for line in group.get("lines", []):
            if line.get("role") != "continuation":
                continue
            entry = entries.get(line.get("offset"))
            if entry is not None:


def source_paths(workspace: Path, selected: list[str] | None) -> list[Path]:
    directory = workspace / "script-pc98" / "MES"
    if selected:
        return [directory / name for name in selected]
    return sorted(directory.glob("*.MES_lang.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=Path(r"C:\work_han\workspace1"))
    parser.add_argument("--files", nargs="+", metavar="LANG_JSON")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    paths = source_paths(workspace, args.files)
    if not paths:
        parser.error("no Necronomicon language JSON files found")

    files = groups = lines = multi = 0
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        document = load_json(path)
        if document.get("format") != FORMAT:
            raise ValueError(f"unexpected format: {path}")
        info = load_json(path.with_name(document["source_info"]))
        display_groups = build_groups(info, document)
        annotate_translated_layout(display_groups, document)
        document["display_groups"] = display_groups
        files += 1
        groups += len(display_groups)
        lines += sum(group["line_count"] for group in display_groups)
        multi += sum(group["has_continuation"] for group in display_groups)
        if not args.dry_run:
            write_json(path, document)
        print(f"{path.name}: groups={len(display_groups)}; multi_line={sum(group['has_continuation'] for group in display_groups)}")
    mode = "preview" if args.dry_run else "written"
    print(f"{mode}: files={files}; groups={groups}; lines={lines}; multi_line_groups={multi}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
