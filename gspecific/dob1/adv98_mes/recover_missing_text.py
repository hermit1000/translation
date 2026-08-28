"""Recover text records omitted by older DOB1 MES decode results.

The source MES files are decoded again with the current decoder and compared
by offset with the existing ``*_info.json`` files. Newly discovered speaker
blocks become dialogue groups; other high-confidence strings become overlays.
Existing dialogue groups and translations are never rewritten.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .decode_mes import decode_document


JAPANESE_TEXT = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
DISPLAY_MACRO_CATEGORIES = {"speaker", "punctuation", "spacing"}
ALLOWED_SINGLE_CHARACTER_TEXTS = {"\u3000\u3000\u9283\u3000\u3000"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def unambiguous_translation(dictionary: dict, original: str) -> str:
    entry = dictionary.get(original, {})
    translated = entry.get("translated", [])
    return translated[0] if len(translated) == 1 else ""


def is_high_confidence(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    return text in ALLOWED_SINGLE_CHARACTER_TEXTS or (
        len(compact) >= 2 and bool(JAPANESE_TEXT.search(text))
    )


def macro_text(catalog: dict, slot: str) -> str:
    macro = catalog.get(slot, {})
    return macro.get("original") or macro.get("translation") or ""


def collect_dialogue(
    records: list[dict], start: int, catalog: dict
) -> tuple[int, dict, str, list[dict]]:
    speaker = records[start]
    segments: list[dict] = []
    macros: list[dict] = []
    display_records = [speaker]
    parts = ["{" + macro_text(catalog, speaker["macro_slot"]) + "}"]
    previous_display_type = "command"
    index = start + 1

    while index < len(records):
        record = records[index]
        if record.get("type") == "command" and record.get("name") == "CALL_BUILTIN":
            slot = record.get("macro_slot")
            if slot == "03":
                break
            definition = catalog.get(slot, {})
            if definition.get("category") in DISPLAY_MACRO_CATEGORIES:
                macros.append({"offset": record["offset"], "slot": slot})
                parts.append("{" + macro_text(catalog, slot) + "}")
                display_records.append(record)
                previous_display_type = "command"
        elif record.get("type") == "text":
            if previous_display_type == "text":
                parts.append("|")
            parts.append(record["original"])
            segments.append({"offset": record["offset"], "end": record["end"]})
            display_records.append(record)
            previous_display_type = "text"
        index += 1

    metadata = {
        "id": f"dialogue:{speaker['offset']}",
        "speaker_slot": speaker["macro_slot"],
        "segments": segments,
        "macros": macros,
    }
    return index, metadata, "".join(parts), display_records


def add_records(info: dict, additions: list[dict]) -> None:
    records = info.setdefault("records", [])
    offsets = {record.get("offset") for record in records}
    for record in additions:
        if record.get("offset") not in offsets:
            records.append(record)
            offsets.add(record.get("offset"))
    records.sort(key=lambda record: int(record["offset"], 16))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workspace", type=Path, nargs="?", default=Path(r"C:\work_han\workspace2")
    )
    parser.add_argument("--write", action="store_true", help="update info/lang JSON files")
    parser.add_argument("--dictionary", type=Path, help="default: <workspace>/dictionary.json")
    parser.add_argument("--report", type=Path, help="default: <workspace>/missing_text_recovery_report.json")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_dir = workspace / "jpn-pc98" / "MES"
    script_dir = workspace / "script-pc98" / "MES"
    dictionary_path = args.dictionary or workspace / "dictionary.json"
    report_path = args.report or workspace / "missing_text_recovery_report.json"
    dictionary = load_json(dictionary_path) if dictionary_path.exists() else {}
    catalog = load_json(Path(__file__).with_name("macro_catalog.json"))["macros"]
    report_entries = []
    summary = {
        "files_checked": 0,
        "files_changed": 0,
        "missing_records": 0,
        "high_confidence_records": 0,
        "dialogue_groups_added": 0,
        "overlays_added": 0,
        "dictionary_translations_applied": 0,
        "translations_needing_review": 0,
    }

    for source_path in sorted(source_dir.glob("*.MES")):
        info_path = script_dir / f"{source_path.name}_info.json"
        lang_path = script_dir / f"{source_path.name}_lang.json"
        if not info_path.exists() or not lang_path.exists():
            continue
        summary["files_checked"] += 1
        info = load_json(info_path)
        lang = load_json(lang_path)
        live_records = decode_document(source_path, source_path.name)["records"]
        old_text_offsets = {
            record.get("offset")
            for record in info.get("records", [])
            if record.get("type") == "text"
        }
        missing_texts = {
            record["offset"]: record
            for record in live_records
            if record.get("type") == "text" and record["offset"] not in old_text_offsets
        }
        if not missing_texts:
            continue

        summary["missing_records"] += len(missing_texts)
        summary["high_confidence_records"] += sum(
            is_high_confidence(record["original"]) for record in missing_texts.values()
        )
        old_dialogue_ids = {item.get("id") for item in info.get("dialogues", [])}
        overlay_offsets = {item.get("offset") for item in lang.get("overlay_texts", [])}
        claimed_offsets: set[str] = set()
        records_to_add: list[dict] = []
        file_entries = []

        index = 0
        while index < len(live_records):
            record = live_records[index]
            definition = catalog.get(record.get("macro_slot", ""), {})
            if not (
                record.get("type") == "command"
                and record.get("name") == "CALL_BUILTIN"
                and definition.get("category") == "speaker"
            ):
                index += 1
                continue
            end, metadata, original, display_records = collect_dialogue(
                live_records, index, catalog
            )
            missing_segments = [
                segment["offset"]
                for segment in metadata["segments"]
                if segment["offset"] in missing_texts
            ]
            if (
                missing_segments
                and metadata["id"] not in old_dialogue_ids
                and any(is_high_confidence(missing_texts[offset]["original"]) for offset in missing_segments)
            ):
                translation = unambiguous_translation(dictionary, original)
                info.setdefault("dialogues", []).append(metadata)
                lang.setdefault("dialogue_groups", []).append(
                    {
                        "id": metadata["id"],
                        "profile_status": "recovered_current_decoder",
                        "original": original,
                        "translation": translation,
                        "status": "pending" if translation else "incomplete: recovered untranslated dialogue",
                    }
                )
                old_dialogue_ids.add(metadata["id"])
                claimed_offsets.update(missing_segments)
                records_to_add.extend(display_records)
                summary["dialogue_groups_added"] += 1
                summary["dictionary_translations_applied"] += bool(translation)
                summary["translations_needing_review"] += not bool(translation)
                file_entries.append(
                    {
                        "kind": "dialogue",
                        "id": metadata["id"],
                        "offsets": missing_segments,
                        "original": original,
                        "translation": translation,
                    }
                )
            index = max(index + 1, end)

        for offset, record in missing_texts.items():
            if offset in claimed_offsets or offset in overlay_offsets:
                continue
            original = record["original"]
            confidence = "high" if is_high_confidence(original) else "review"
            translation = unambiguous_translation(dictionary, original)
            if confidence == "high":
                lang.setdefault("overlay_texts", []).append(
                    {
                        "offset": offset,
                        "original": original,
                        "translation": translation,
                        "status": "pending" if translation else "incomplete: recovered untranslated overlay",
                    }
                )
                records_to_add.append(record)
                overlay_offsets.add(offset)
                summary["overlays_added"] += 1
                summary["dictionary_translations_applied"] += bool(translation)
                summary["translations_needing_review"] += not bool(translation)
            file_entries.append(
                {
                    "kind": "overlay" if confidence == "high" else "review",
                    "offset": offset,
                    "original": original,
                    "translation": translation,
                    "confidence": confidence,
                }
            )

        if records_to_add:
            add_records(info, records_to_add)
            info.setdefault("dialogues", []).sort(
                key=lambda item: int(item["id"].split(":", 1)[1], 16)
            )
            lang.setdefault("dialogue_groups", []).sort(
                key=lambda item: int(item["id"].split(":", 1)[1], 16)
            )
            lang.setdefault("overlay_texts", []).sort(
                key=lambda item: int(item["offset"], 16)
            )
            summary["files_changed"] += 1
            if args.write:
                info_path.write_text(
                    json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                lang_path.write_text(
                    json.dumps(lang, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
        report_entries.append({"file": source_path.name, "entries": file_entries})

    report = {
        "format": "dob1-current-decoder-missing-text-v1",
        "workspace": str(workspace),
        "mode": "write" if args.write else "dry-run",
        "summary": summary,
        "files": report_entries,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
