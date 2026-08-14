#!/usr/bin/env python3
"""Link existing Korean binary inputs to Nobu2 384 KB script JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from gspecific.nobu2.decode_graphics_384k import (
    HYOSI_RECORDS,
    MAP_RECORDS,
    ODAMAIN_COUNT,
    ODAMAIN_RECORD_SIZE,
    ODAMAIN_TABLE_OFFSET,
)


OLD_ODAMAIN_OFFSETS = (
    0x18652,
    0x186B4,
    0x18716,
    0x18778,
    0x187DA,
    0x1883C,
    0x1889E,
)

HYOSI_INPUTS = {
    "TITLE.PAK": "TITLE.PAK/TITLE.PAK",
    "END2.PAK": "END2.PAK/END2.PAK",
}

N_DATA_PLANAR_OFFSETS = (
    0x006CF,
    0x00731,
    0x00793,
    0x007F5,
    0x00857,
    0x008B9,
    0x0091B,
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("c:/work_han/workspace0"),
        help="workspace containing binary_inputs-pc98 and 384 KB scripts",
    )
    parser.add_argument("--save", action="store_true", help="write the 384 KB script JSON files")
    return parser.parse_args()


def address(offset: int, size: int):
    return f"{offset:05X}={offset + size - 1:05X}"


def same_pixels(first: Path, second: Path):
    image_a = Image.open(first).convert("RGB")
    image_b = Image.open(second).convert("RGB")
    return image_a.size == image_b.size and list(image_a.getdata()) == list(image_b.getdata())


def update_binary_input(path: Path, entries: dict[str, str], save: bool):
    content = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as file:
            content = json.load(file)
    content.pop("binary_input", None)
    updated = {"binary_input": entries, **content}
    if save:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\r\n") as file:
            json.dump(updated, file, ensure_ascii=False, indent=4)


def ensure_empty_jpn(path: Path, save: bool):
    if path.exists():
        return
    if save:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8", newline="\r\n")


def prepare_odamain(workspace: Path, save: bool):
    old_images = workspace / "image-pc98/ODAMAIN.EXE"
    new_images = workspace / "image-pc98-384k/ODAMAIN.EXE"
    entries = {}
    details = []

    for index in range(ODAMAIN_COUNT):
        old_offset = OLD_ODAMAIN_OFFSETS[index]
        new_offset = ODAMAIN_TABLE_OFFSET + index * ODAMAIN_RECORD_SIZE + 2
        old_stem = f"{old_offset:06X}"
        new_stem = f"{new_offset:06X}"
        if not same_pixels(
            old_images / f"{old_stem}.jpn.png",
            new_images / f"{new_stem}.jpn.png",
        ):
            raise ValueError(f"ODAMAIN frame mismatch: {old_stem} != {new_stem}")

        relative = f"ODAMAIN.EXE/{old_stem}.pln.kor.bin"
        binary_path = workspace / "binary_inputs-pc98" / relative
        size = binary_path.stat().st_size
        entries[address(new_offset, size)] = relative
        details.append(
            {
                "old_offset": f"0x{old_offset:06X}",
                "new_offset": f"0x{new_offset:06X}",
                "input": relative,
                "size": size,
            }
        )

    update_binary_input(
        workspace / "script-pc98-384k/ODAMAIN.EXE_kor.json",
        entries,
        save,
    )
    return entries, details


def prepare_n_data(workspace: Path, save: bool):
    entries = {}
    details = []
    for old_offset, new_offset in zip(OLD_ODAMAIN_OFFSETS, N_DATA_PLANAR_OFFSETS):
        relative = f"ODAMAIN.EXE/{old_offset:06X}.pln.kor.bin"
        binary_path = workspace / "binary_inputs-pc98" / relative
        size = binary_path.stat().st_size
        entries[address(new_offset, size)] = relative
        details.append(
            {
                "offset": f"0x{new_offset:06X}",
                "input": relative,
                "size": size,
            }
        )

    for file_name in ("DATA17N.DAT", "DATA50N.DAT"):
        update_binary_input(
            workspace / f"script-pc98-384k/{file_name}_kor.json",
            entries,
            save,
        )
    return entries, details


def prepare_hyosi(workspace: Path, save: bool):
    binary_inputs = workspace / "binary_inputs-pc98"
    target_size = (workspace / "jpn-pc98-384k/HYOSI.DAT").stat().st_size
    entries = {}
    details = []

    for index, (record_offset, name, _width, _height, _literal_rows, _copy_rows) in enumerate(HYOSI_RECORDS):
        relative = HYOSI_INPUTS.get(name)
        if relative is None:
            continue
        binary_path = binary_inputs / relative
        size = binary_path.stat().st_size
        payload_offset = record_offset + 4
        next_offset = HYOSI_RECORDS[index + 1][0] if index + 1 < len(HYOSI_RECORDS) else target_size
        capacity = next_offset - payload_offset
        if size > capacity:
            raise ValueError(f"{relative}: size {size} exceeds HYOSI.DAT slot {capacity}")
        entries[address(payload_offset, size)] = relative
        details.append(
            {
                "name": name,
                "offset": f"0x{payload_offset:06X}",
                "input": relative,
                "size": size,
                "capacity": capacity,
            }
        )

    ensure_empty_jpn(workspace / "script-pc98-384k/HYOSI.DAT_jpn.json", save)
    update_binary_input(
        workspace / "script-pc98-384k/HYOSI.DAT_kor.json",
        entries,
        save,
    )
    return entries, details


def prepare_map(workspace: Path, save: bool):
    binary_inputs = workspace / "binary_inputs-pc98"
    target_size = (workspace / "jpn-pc98-384k/MAP.DAT").stat().st_size
    entries = {}
    details = []
    skipped = []

    for index, (record_offset, name, _width, _height, _literal_rows, _copy_rows) in enumerate(MAP_RECORDS):
        relative = f"MAP/{name}"
        binary_path = binary_inputs / relative
        if not binary_path.exists():
            skipped.append({"name": name, "reason": "Korean binary input does not exist"})
            continue
        size = binary_path.stat().st_size
        payload_offset = record_offset + 4
        next_offset = MAP_RECORDS[index + 1][0] if index + 1 < len(MAP_RECORDS) else target_size
        capacity = next_offset - payload_offset
        if size > capacity:
            skipped.append(
                {
                    "name": name,
                    "reason": "existing binary exceeds 384 KB slot",
                    "size": size,
                    "capacity": capacity,
                    "excess": size - capacity,
                }
            )
            continue
        entries[address(payload_offset, size)] = relative
        details.append(
            {
                "name": name,
                "offset": f"0x{payload_offset:06X}",
                "input": relative,
                "size": size,
                "capacity": capacity,
            }
        )

    ensure_empty_jpn(workspace / "script-pc98-384k/MAP.DAT_jpn.json", save)
    update_binary_input(
        workspace / "script-pc98-384k/MAP.DAT_kor.json",
        entries,
        save,
    )
    return entries, details, skipped


def prepare_all(workspace: Path, save: bool = True):
    odamain_entries, odamain_details = prepare_odamain(workspace, save)
    n_data_entries, n_data_details = prepare_n_data(workspace, save)
    hyosi_entries, hyosi_details = prepare_hyosi(workspace, save)
    map_entries, map_details, skipped = prepare_map(workspace, save)
    report = {
        "ODAMAIN.EXE": {"binary_input": odamain_entries, "frames": odamain_details},
        "DATA17N.DAT": {"binary_input": n_data_entries, "frames": n_data_details},
        "DATA50N.DAT": {"binary_input": n_data_entries, "frames": n_data_details},
        "HYOSI.DAT": {"binary_input": hyosi_entries, "records": hyosi_details},
        "MAP.DAT": {"binary_input": map_entries, "records": map_details, "skipped": skipped},
    }
    if save:
        report_path = workspace / "script-pc98-384k/graphics_binary_input_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )

    print(f"ODAMAIN.EXE: linked {len(odamain_entries)} existing input(s)")
    print(f"DATA17N.DAT: linked {len(n_data_entries)} existing input(s)")
    print(f"DATA50N.DAT: linked {len(n_data_entries)} existing input(s)")
    print(f"HYOSI.DAT: linked {len(hyosi_entries)} existing input(s)")
    print(f"MAP.DAT: linked {len(map_entries)} existing input(s), skipped {len(skipped)}")
    for item in skipped:
        print(f"  skipped {item['name']}: {item['reason']}")
    return report


def main():
    args = parse_args()
    prepare_all(args.workspace, args.save)
    if not args.save:
        print("Dry run only. Use --save to write JSON files.")


if __name__ == "__main__":
    main()
