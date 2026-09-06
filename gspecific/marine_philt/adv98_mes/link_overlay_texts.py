"""Annotate overlay entries with text links proven by adjacent BA 27 BA 23 calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


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

    for before, wait, advance, after in zip(records, records[1:], records[2:], records[3:]):
        if (
            before.get("type") == after.get("type") == "text"
            and is_call(wait, 4)
            and is_call(advance, 0)
        ):
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    changed = linked = 0
    for path in sorted((args.workspace / "script-pc98" / "MES").glob("*_lang.json")):
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
