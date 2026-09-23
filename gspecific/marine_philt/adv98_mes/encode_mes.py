#!/usr/bin/env python3
"""Encode Marine Philt MES using the shared DOB2-compatible record adapter."""

from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Any

from gspecific.dob2.adv98_mes.encode_mes import main as encode_main

from .refresh_cell_analysis import refresh as refresh_cell_analysis


NEXT_MARKER = "{next}"
DISPLAY_LINE_CELLS = 27
SPEAKER_RESERVE_CELLS = 4
FULL_SEGMENT_CELLS = DISPLAY_LINE_CELLS * 3
NEXT_SEGMENT_CELLS = FULL_SEGMENT_CELLS - SPEAKER_RESERVE_CELLS

FONT_FALLBACKS = str.maketrans({"·": "・", "'": "’"})
CATALOG_PATH = Path(__file__).resolve().parents[1] / "speaker_control_catalog.json"
MARINE_REMAP_PATH = Path(__file__).resolve().parents[1] / "marine_compact_font_mapping_top20.json"


def patch_staff_credit_layout(info: dict[str, Any], data: bytes) -> bytes:
    """Move the STAFF technical-adviser block left by two fullwidth cells.

    The leading spaces are a non-editable layout record. Adjust the preceding
    cursor-position command instead of changing the record length, because MES
    contains position-sensitive offsets after this block.
    """
    if Path(str(info.get("source", ""))).name.upper() != "STAFF_CR.MES":
        return data
    marker = bytes.fromhex(
        "AC 29 04 58 23 AA 23 81 40 81 40 81 40 81 40 21 "
        "54 45 43 48 4E 49 43 41 4C 20 41 44 56 49 53 45 52"
    )
    replacement = bytes.fromhex(
        "AC 29 03 58 23 AA 23 81 40 81 40 81 40 81 40 21 "
        "54 45 43 48 4E 49 43 41 4C 20 41 44 56 49 53 45 52"
    )
    occurrences = data.count(marker)
    if occurrences != 1:
        raise ValueError(
            f"STAFF_CR technical-adviser layout marker count is {occurrences}, expected 1"
        )
    patched = data.replace(marker, replacement, 1)
    # Keep the two standalone RUSH-TEAM records and their line controls, but
    # blank only the labels so the three-name credit layout remains intact.
    return patched.replace(b"(RUSH-TEAM)", b" " * len("(RUSH-TEAM)"))


def load_control_speaker_catalog() -> dict[str, Any]:
    if not CATALOG_PATH.is_file():
        return {"unknown_policy": "warn_and_use_zero", "files": {}}
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def control_speaker_cells(
    info: dict[str, Any], record: dict[str, Any], catalog: dict[str, Any],
    *, text_offset: str | None = None,
    translation_preview: str | None = None,
) -> int:
    source_name = Path(str(info.get("source", ""))).name
    file_catalog = catalog.get("files", {}).get(source_name, {})
    text_item = file_catalog.get("text_offsets", {}).get(text_offset)
    if text_item is not None:
        return int(text_item["cells"])
    raw_hex = str(record.get("raw_hex", ""))
    parts = raw_hex.split()
    control_id = parts[1].upper() if len(parts) >= 2 else ""
    # 01/02/03 are common Marine setup/control values, not speaker IDs.
    # Treating them as speakers causes false warnings for UI overlays such as
    # the standalone "wallet" label at 0205B in 000001.MES.
    if control_id in {"01", "02", "03"}:
        return 0
    item = file_catalog.get(control_id)
    if item is not None:
        return int(item["cells"])
    preview = (translation_preview or "").replace("\r", " ").replace("\n", " ")[:40]
    print(
        f"WARNING: unknown Marine control speaker {source_name} 08 {control_id} "
        f"before {text_offset or '?'}; "
        f"reserving {SPEAKER_RESERVE_CELLS} prefix cells"
        + (f"; translation={preview!r}" if preview else ""),
        file=sys.stderr,
    )
    return SPEAKER_RESERVE_CELLS


def normalize_font_characters(lang: dict[str, Any]) -> None:
    """Use visually equivalent glyphs available in the Korean font table.

    The editable translation remains unchanged; the temporary values are
    restored by ``restore_connected_translations`` after encoding.
    """
    for section in ("dialogue_groups", "overlay_texts"):
        for entry in lang.get(section, []):
            value = entry.get("translation")
            if isinstance(value, str) and value and value != "@keep":
                entry["_marine_original_translation"] = value
                entry["translation"] = value.translate(FONT_FALLBACKS)


def annotate_control_speaker_cells(info: dict[str, Any], lang: dict[str, Any]) -> None:
    """Account for speaker labels rendered by preceding 08 xx controls."""
    catalog = load_control_speaker_catalog()
    records = sorted(info.get("records", []), key=lambda r: int(r["offset"], 16))
    by_offset = {record["offset"]: index for index, record in enumerate(records)}
    for section in ("dialogue_groups", "overlay_texts"):
        for entry in lang.get(section, []):
            entry.pop("_display_prefix_cells", None)
            value = entry.get("translation")
            if not isinstance(value, str) or not value or value == "@keep":
                continue
            # A literal [speaker] is already part of the editable text.
            if value.lstrip().startswith(("[", "〔")):
                continue
            index = by_offset.get(entry.get("offset"))
            if index is None:
                continue
            # The Marine control sequence is immediately before the text
            # record, but may be preceded by BA/TCM setup commands.
            speaker_record = None
            for record in reversed(records[:index]):
                if record.get("type") == "text":
                    break
                if record.get("type") == "control" and record.get("raw_hex", "").startswith("08 "):
                    speaker_record = record
                    break
            if speaker_record is not None:
                source_name = Path(str(info.get("source", ""))).name
                text_item = (
                    catalog.get("files", {})
                    .get(source_name, {})
                    .get("text_offsets", {})
                    .get(entry.get("offset"))
                )
                if text_item is not None:
                    entry["_display_prefix_cells"] = int(text_item["cells"])
                else:
                    entry["_display_prefix_cells"] = control_speaker_cells(
                        info,
                        speaker_record,
                        catalog,
                        text_offset=entry.get("offset"),
                        translation_preview=value,
                    )
            else:
                # Some Marine dialogue records render a speaker label without
                # an immediately preceding 08 xx record. Use a confirmed
                # per-text catalog entry for line-boundary calculations.
                source_name = Path(str(info.get("source", ""))).name
                text_item = (
                    catalog.get("files", {})
                    .get(source_name, {})
                    .get("text_offsets", {})
                    .get(entry.get("offset"))
                )
                if text_item is not None:
                    entry["_display_prefix_cells"] = int(text_item["cells"])


def prepare_connected_translations(
    info: dict[str, Any],
    lang: dict[str, Any],
    *,
    check_segment_length: bool = True,
    suppress_trailing_transition_offset: str | None = None,
    suppress_trailing_control_offset: str | None = None,
) -> dict[str, list[tuple[int, int]]]:
    """Split explicitly marked Marine connected translations by source record."""
    normalize_font_characters(lang)
    annotate_control_speaker_cells(info, lang)
    entries = {
        entry["offset"]: entry
        for section in ("dialogue_groups", "overlay_texts")
        for entry in lang.get(section, [])
    }
    ordered_records = sorted(info["records"], key=lambda record: int(record["offset"], 16))
    records = {record["offset"]: record for record in ordered_records}
    skip_ranges: list[tuple[int, int]] = []
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
        marked = [offset for offset in ordered if NEXT_MARKER in entries[offset].get("translation", "")]
        if not marked:
            if (
                entries[ordered[0]].get("combined_original")
                and any(not entries[offset].get("translation") for offset in ordered[1:])
                and entries[ordered[0]].get("translation")
            ):
                raise ValueError(
                    f"connected Marine translation at {ordered[0]} needs {{next}} "
                    "or translations for every connected record"
                )
            continue
        if len(marked) != 1:
            raise ValueError(
                "connected Marine translations must contain {next} in exactly one entry: "
                + ", ".join(ordered)
            )
        combined = entries[marked[0]]["translation"]
        parts = combined.split(NEXT_MARKER)
        if len(parts) != len(ordered):
            raise ValueError(
                f"connected Marine translation at {marked[0]} needs "
                f"{len(ordered) - 1} {{next}} marker(s), got {len(parts) - 1}"
            )
        # A literal [speaker] is already included in the segment length.
        # Reserve four cells only when the game renders the speaker outside
        # the editable translation.
        has_literal_speaker = parts[0].lstrip().startswith(("[", "〔"))
        has_hidden_speaker = bool(entries[marked[0]].get("_display_prefix_cells"))
        segment_limit = (
            NEXT_SEGMENT_CELLS
            if has_hidden_speaker and not has_literal_speaker
            else FULL_SEGMENT_CELLS
        )
        oversized = [
            (index, len(part))
            for index, part in enumerate(parts, 1)
            if len(part) > segment_limit
        ]
        if oversized and check_segment_length:
            details = ", ".join(f"segment {index}: {length} cells" for index, length in oversized)
            raise ValueError(
                f"Marine {{next}} segment exceeds {segment_limit} cells "
                f"({DISPLAY_LINE_CELLS} cells x 3 lines, speaker reserve applied when hidden) at "
                f"{marked[0]} ({details}); shorten or move {{next}} before encoding"
            )
        if oversized and not check_segment_length:
            details = ", ".join(f"segment {index}: {length} cells" for index, length in oversized)
            print(
                f"WARNING: Marine {{next}} segment exceeds {NEXT_SEGMENT_CELLS} cells "
                f"at {marked[0]} ({details}); continuing because length checking is disabled",
                file=sys.stderr,
            )
        trailing_skip = not parts[-1].strip()
        if any(not part.strip() for part in parts[:-1]) or (not trailing_skip and any(not part.strip() for part in parts)):
            raise ValueError(
                f"connected Marine translation at {marked[0]} has an empty {{next}} segment"
            )
        entries[marked[0]]["_next_combined_translation"] = combined
        for offset in ordered:
            entries[offset]["_next_restore_root"] = marked[0]
        for offset, part in zip(ordered, parts):
            entries[offset]["translation"] = part
        if trailing_skip:
            previous = records[ordered[-2]]
            skipped = records[ordered[-1]]
            if marked[0] == suppress_trailing_control_offset:
                skip_ranges.append((int(skipped["offset"], 16), int(skipped["end"], 16)))
                after_skipped = [
                    record
                    for record in ordered_records
                    if int(record["offset"], 16) > int(skipped["end"], 16)
                ]
                control = next(
                    (
                        record
                        for record in after_skipped
                        if record.get("type") == "control"
                        and record.get("value") == "CONTROL_0C"
                    ),
                    None,
                )
                if control is None:
                    raise ValueError(
                        f"cannot find trailing CONTROL_0C after {skipped['offset']}"
                    )
                control_start = int(control["offset"], 16)
                control_length = len(bytes.fromhex(control.get("raw_hex", "")))
                skip_ranges.append((control_start, control_start + control_length - 1))
            elif marked[0] == suppress_trailing_transition_offset:
                # Keep the BA27/BA23 transition after the displayed record,
                # remove only the unused linked text and the following
                # transition commands through the record immediately before
                # the cursor-reset command.  Keep AA/F6_0B and END_FFFF so
                # the next dialogue can still advance normally.  This is an
                # experimental, per-entry path for diagnosing trailing
                # {next} scroll behavior.
                skip_ranges.append((int(skipped["offset"], 16), int(skipped["end"], 16)))
                after_skipped = [
                    record
                    for record in ordered_records
                    if int(record["offset"], 16) > int(skipped["end"], 16)
                ]
                cursor_reset = next(
                    (
                        record
                        for record in after_skipped
                        if record.get("name") == "F6_0B_AND_CURSOR_RESET"
                    ),
                    None,
                )
                if cursor_reset is None:
                    raise ValueError(
                        f"cannot find cursor reset after {skipped['offset']}"
                    )
                transition_end = int(cursor_reset["offset"], 16) - 1
                skip_ranges.append(
                    (int(skipped["end"], 16) + 1, transition_end)
                )
            else:
                skip_ranges.append((int(previous["end"], 16) + 1, int(skipped["end"], 16)))

    return {"skip_ranges": skip_ranges}


def restore_connected_translations(info: dict[str, Any], lang: dict[str, Any]) -> None:
    """Restore the editable combined translation after temporary encoding splits."""
    for section in ("dialogue_groups", "overlay_texts"):
        for entry in lang.get(section, []):
            combined = entry.pop("_next_combined_translation", None)
            root = entry.pop("_next_restore_root", None)
            if root is not None and entry["offset"] != root:
                # Linked child cells are encoded from the root's {next}
                # translation. Keep an explicit marker in the editable JSON
                # instead of exposing an apparently missing translation.
                entry["translation"] = "@keep"
                entry["status"] = "linked: edit the earliest connected entry"
            elif combined is not None:
                entry["translation"] = combined
            original = entry.pop("_marine_original_translation", None)
            if original is not None:
                entry["translation"] = original
            entry.pop("_display_prefix_cells", None)
    refresh_cell_analysis(lang)


def main() -> int:
    allow_oversize = "--allow-oversize-segments" in sys.argv
    if allow_oversize:
        sys.argv.remove("--allow-oversize-segments")
    suppress_transition_offset = None
    if "--suppress-trailing-transition" in sys.argv:
        index = sys.argv.index("--suppress-trailing-transition")
        try:
            suppress_transition_offset = sys.argv[index + 1]
        except IndexError as exc:
            raise ValueError("--suppress-trailing-transition requires an entry offset") from exc
        del sys.argv[index : index + 2]
    suppress_control_offset = None
    if "--suppress-trailing-control" in sys.argv:
        index = sys.argv.index("--suppress-trailing-control")
        try:
            suppress_control_offset = sys.argv[index + 1]
        except IndexError as exc:
            raise ValueError("--suppress-trailing-control requires an entry offset") from exc
        del sys.argv[index : index + 2]
    # Existing boundary convention: 28 denotes a 27-cell display line.
    return encode_main(
        width=28,
        speaker_repairs=False,
        preprocess_lang=lambda info, lang: prepare_connected_translations(
            info,
            lang,
            check_segment_length=not allow_oversize,
            suppress_trailing_transition_offset=suppress_transition_offset,
            suppress_trailing_control_offset=suppress_control_offset,
        ),
        postprocess_lang=restore_connected_translations,
        postprocess_output=patch_staff_credit_layout,
        default_marine_remap=MARINE_REMAP_PATH,
    )


if __name__ == "__main__":
    raise SystemExit(main())
