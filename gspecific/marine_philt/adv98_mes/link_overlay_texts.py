"""Annotate overlay entries with text links proven by adjacent BA 27 BA 23 calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


NEXT_MARKER = "{next}"


def annotate_connections(info: dict, lang: dict) -> None:
    entries = {
        entry["offset"]: entry
        for section in ("dialogue_groups", "overlay_texts")
        for entry in lang.get(section, [])
    }
    records = info["records"]
    source_records = {record["offset"]: record for record in records}
    for offset, entry in entries.items():
        record = source_records.get(offset)
        if not record or record.get("original") != entry["original"]:
            raise ValueError(f"original mismatch at {offset}")
    neighbors: dict[str, set[str]] = {}

    def is_call(record: dict, value: int) -> bool:
        arguments = record.get("arguments", [])
        return (
            record.get("type") == "command"
            and record.get("opcode") == "BA"
            and len(arguments) == 1
            and arguments[0].get("type") == "argument"
            and arguments[0].get("value") == value
        )

    for index, before in enumerate(records):
        if before.get("type") != "text":
            continue
        for gap, prefix_length in ((3, 0), (4, 1), (5, 1)):
            if index + gap >= len(records):
                continue
            after = records[index + gap]
            if after.get("type") != "text":
                continue
            wait_index = index + 1 + prefix_length
            advance_index = wait_index + 1
            if gap == 5:
                spacer = records[index + 4]
                if spacer.get("type") != "command" or spacer.get("opcode") != "C5":
                    continue
            if (
                prefix_length == 0
                or is_call(records[index + 1], 3)
            ) and is_call(records[wait_index], 4) and is_call(records[advance_index], 0):
                left, right = before["offset"], after["offset"]
                neighbors.setdefault(left, set()).add(right)
                neighbors.setdefault(right, set()).add(left)

    for overlay in lang.get("overlay_texts", []):
        start = overlay["offset"]
        visited = {start}
        pending = [start]
        while pending:
            for offset in neighbors.get(pending.pop(), ()):
                if offset not in visited:
                    visited.add(offset)
                    pending.append(offset)
        overlay["connections"] = [
            {"id": entries[offset]["id"], "offset": offset}
            for offset in sorted(visited - {start}, key=lambda value: int(value, 16))
            if offset in entries
        ]

    graph = {offset: set() for offset in entries}
    for entry in entries.values():
        for connection in entry.get("connections", []):
            other = connection.get("offset")
            if other in entries:
                graph[entry["offset"]].add(other)
                graph[other].add(entry["offset"])
    visited: set[str] = set()
    for start in sorted(graph, key=lambda value: int(value, 16)):
        if start in visited:
            continue
        pending = [start]
        component: set[str] = set()
        while pending:
            offset = pending.pop()
            if offset in component:
                continue
            component.add(offset)
            pending.extend(graph[offset] - component)
        visited.update(component)
        if len(component) < 2:
            continue
        ordered = sorted(component, key=lambda value: int(value, 16))
        root = entries[ordered[0]]
        root["combined_original"] = NEXT_MARKER.join(entries[offset]["original"] for offset in ordered)
        root.pop("combined_segments", None)
        translations = [entries[offset].get("translation", "") for offset in ordered]
        marked_translation = any(NEXT_MARKER in translation for translation in translations)
        if not marked_translation and any(translations):
            root["translation"] = NEXT_MARKER.join(translations)
            root["status"] = (
                "passed"
                if all(translations)
                else "incomplete: connected translation"
            )
            for offset in ordered[1:]:
                entries[offset]["translation"] = ""
                entries[offset]["status"] = "linked: edit the earliest connected entry"
        elif marked_translation:
            for offset in ordered[1:]:
                entries[offset]["translation"] = ""
                entries[offset]["status"] = "linked: edit the earliest connected entry"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--files", nargs="+", metavar="JSON")
    args = parser.parse_args()
    changed = linked = 0
    paths = (
        [args.workspace / "script-pc98" / "MES" / name for name in args.files]
        if args.files
        else sorted((args.workspace / "script-pc98" / "MES").glob("*_lang.json"))
    )
    for path in paths:
        lang = json.loads(path.read_text(encoding="utf-8"))
        if lang.get("format") != "marine-philt-adv98-mes-lang-v1":
            raise ValueError(f"unexpected format: {path}")
        info_name = lang["source_info"]
        if Path(info_name).name != info_name:
            raise ValueError(f"expected an info filename: {info_name}")
        info = json.loads(path.with_name(info_name).read_text(encoding="utf-8"))
        previous = json.dumps(lang, ensure_ascii=False)
        annotate_connections(info, lang)
        linked += sum(bool(entry["connections"]) for entry in lang.get("overlay_texts", []))
        if json.dumps(lang, ensure_ascii=False) != previous:
            text = json.dumps(lang, ensure_ascii=False, indent=2) + "\n"
            path.write_text(text.replace("\n", "\r\n"), encoding="utf-8", newline="")
            changed += 1
    print(f"updated files: {changed}; overlays with connections: {linked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
