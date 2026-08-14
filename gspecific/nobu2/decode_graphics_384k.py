#!/usr/bin/env python3
"""Decode Nobunaga Zenkokuban 384 KB PC-98 graphics."""

from __future__ import annotations

import argparse
import hashlib
import struct
from collections import Counter
from pathlib import Path

from PIL import Image

from gspecific.image_workspace import ImageWorkspace, offset_stem
from gspecific.nobu2.decode_graphics import (
    finish_report,
    hex_offset,
    save_frame,
    save_sheet,
)
from gspecific.nobu2.pc98_image_codec import decode_pak, decode_planar
from module.pc98_image.palette import PC98_PALETTE_3BPP

ODAMAIN_TABLE_OFFSET = 0xA40C
ODAMAIN_RECORD_SIZE = 0x62
ODAMAIN_COUNT = 7

KAO_SECTIONS = (
    ("BUSYOU", 0x00000, 53, 64, 40),
    ("MONTAGU", 0x0C800, 4, 64, 40),
    ("HIME", 0x0D800, 20, 88, 48),
)

MAP_RECORDS = (
    (0x00000, "MAP17.PAK", 512, 160, 2, 2),
    (0x02C00, "ZENKOKU.PAK", 512, 160, 2, 2),
    (0x05A00, "KINKI.PAK", 512, 160, 2, 2),
    (0x08800, "HOKURIKU.PAK", 512, 160, 2, 2),
    (0x0B000, "TOUHOKU.PAK", 512, 160, 2, 2),
    (0x0D800, "SHIKOKU.PAK", 512, 160, 2, 2),
    (0x10E00, "KANTOU.PAK", 512, 160, 2, 2),
    (0x13E00, "KYUSYU.PAK", 512, 160, 2, 2),
    (0x16800, "TYUBU.PAK", 512, 160, 2, 2),
)

HYOSI_RECORDS = (
    (0x0000, "TITLE.PAK", 640, 183, 4, 4),
    (0x3600, "END1.PAK", 640, 200, 2, 2),
    (0xA400, "END2.PAK", 640, 200, 2, 2),
)

ODAANM_SEQUENCE_OFFSETS = (
    0x00000,
    0x00E00,
    0x05C00,
    0x06C00,
    0x08200,
    0x09A00,
    0x0AA00,
    0x0CC00,
    0x10400,
    0x12000,
    0x13C00,
    0x15E00,
    0x16E00,
    0x17E00,
    0x1BC00,
    0x1D000,
    0x20E00,
    0x22400,
    0x23400,
    0x27200,
    0x28800,
    0x29A00,
    0x2BA00,
)

SEISHIGA_SPECS = (
    (0x0000, 120, 32),
    (0x0600, 136, 32),
    (0x0E00, 136, 32),
    (0x1600, 136, 32),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_odamain(
    source: Path,
    output: Path,
    *,
    all_artifacts: bool = False,
) -> dict[str, object]:
    data = source.read_bytes()
    required = ODAMAIN_TABLE_OFFSET + ODAMAIN_COUNT * ODAMAIN_RECORD_SIZE
    if data[:2] != b"MZ" or len(data) < required:
        raise ValueError("unsupported or truncated 384 KB ODAMAIN.EXE")
    output.mkdir(parents=True, exist_ok=True)
    frames = []
    images = []
    for index in range(ODAMAIN_COUNT):
        record_offset = ODAMAIN_TABLE_OFFSET + index * ODAMAIN_RECORD_SIZE
        x_byte, screen_y = data[record_offset : record_offset + 2]
        payload_offset = record_offset + 2
        planar = data[payload_offset : payload_offset + 48]
        image, _pixels = decode_planar(planar, 16, 8)
        frame = save_frame(
            output,
            image,
            planar,
            payload_offset,
            all_artifacts=all_artifacts,
        )
        frame.update(
            {
                "index": index,
                "record_offset": hex_offset(record_offset),
                "screen_x": x_byte * 8,
                "screen_y": screen_y,
            }
        )
        frames.append(frame)
        images.append(image)
    if all_artifacts:
        save_sheet(images, output / "sheet.png", columns=7, scale=4)
    return finish_report(
        output,
        {
            "source": source.name,
            "source_sha256": sha256(data),
            "format": "7 fixed EXE records with 16x8 interleaved B/R/G planar data",
            "table_offset": hex_offset(ODAMAIN_TABLE_OFFSET),
            "frames": frames,
        },
    )


def decode_kao(
    source: Path,
    output: Path,
    *,
    all_artifacts: bool = False,
) -> dict[str, object]:
    data = source.read_bytes()
    output.mkdir(parents=True, exist_ok=True)
    frames = []
    images = []
    sections = []
    for section_name, section_offset, count, width, height in KAO_SECTIONS:
        frame_size = width // 8 * height * 3
        for index in range(count):
            offset = section_offset + index * frame_size
            planar = data[offset : offset + frame_size]
            if len(planar) != frame_size:
                raise EOFError(f"{source.name}: frame at {hex_offset(offset)} is truncated")
            image, _pixels = decode_planar(planar, width, height)
            frame = save_frame(
                output,
                image,
                planar,
                offset,
                all_artifacts=all_artifacts,
            )
            frame.update({"section": section_name, "index": index})
            frames.append(frame)
            images.append(image)
        sections.append(
            {
                "name": section_name,
                "offset": hex_offset(section_offset),
                "count": count,
                "width": width,
                "height": height,
                "frame_size": frame_size,
            }
        )
    if all_artifacts:
        save_sheet(images, output / "sheet.png")
    return finish_report(
        output,
        {
            "source": source.name,
            "source_sha256": sha256(data),
            "format": "three aligned raw interleaved B/R/G portrait sections",
            "sections": sections,
            "frames": frames,
        },
    )


def decode_pak_container(
    source: Path,
    output: Path,
    records: tuple[tuple[int, str, int, int, int, int], ...],
    *,
    all_artifacts: bool = False,
) -> dict[str, object]:
    data = source.read_bytes()
    output.mkdir(parents=True, exist_ok=True)
    frames = []
    images = []
    for index, (record_offset, name, width, height, literal_rows, copy_rows) in enumerate(records):
        next_offset = records[index + 1][0] if index + 1 < len(records) else len(data)
        stored_width, stored_height = struct.unpack_from("<HH", data, record_offset)
        if stored_width != width or stored_height not in {height, height - 1}:
            raise ValueError(
                f"{source.name} at {hex_offset(record_offset)} has unexpected "
                f"dimensions {stored_width}x{stored_height}"
            )
        payload_offset = record_offset + 4
        block = data[payload_offset:next_offset]
        image, planar, pixels, info = decode_pak(
            block,
            width,
            height,
            literal_rows,
            copy_rows,
        )
        stem = offset_stem(payload_offset)
        png_name = f"{stem}.jpn.png"
        image.save(output / png_name)
        files = {"png": png_name}
        if all_artifacts:
            compressed_name = f"{stem}.cmp.jpn.bin"
            planar_name = f"{stem}.pln.jpn.bin"
            pixels_name = f"{stem}.idx.jpn.bin"
            (output / compressed_name).write_bytes(block)
            (output / planar_name).write_bytes(planar)
            (output / pixels_name).write_bytes(pixels)
            files.update(
                {
                    "compressed": compressed_name,
                    "planar": planar_name,
                    "pixels": pixels_name,
                }
            )
        frames.append(
            {
                "name": name,
                "record_offset": hex_offset(record_offset),
                "offset": hex_offset(payload_offset),
                "width": width,
                "height": height,
                "stored_size": len(block),
                **info,
                "files": files,
            }
        )
        images.append(image)
    if all_artifacts:
        save_sheet(images, output / "sheet.png", columns=3)
    return finish_report(
        output,
        {
            "source": source.name,
            "source_sha256": sha256(data),
            "format": "4-byte dimensions plus Nobu2 0x96 vertical-copy PAK records",
            "frames": frames,
        },
    )


def parse_odaanm_script(
    script: bytes,
) -> tuple[int, int, int, list[dict[str, int]]]:
    position = 0
    width_bytes = height = allocation_blocks = -1
    default_y = 0
    references = []
    while position < len(script):
        command_offset = position
        command = script[position]
        position += 1
        if command == ord("A"):
            width_bytes, height = script[position : position + 2]
            position += 2
        elif command == ord("B"):
            allocation_blocks = script[position]
            position += 1
        elif command == ord("C"):
            position += 5
        elif command == ord("D"):
            end = script.find(b"\0", position)
            if end < 0:
                break
            position = end + 1
        elif command in map(ord, "ELORW"):
            continue
        elif command in map(ord, "PQ"):
            references.append(
                {
                    "command_offset": command_offset,
                    "block": script[position],
                    "screen_x": script[position + 1] * 8,
                    "screen_y": default_y,
                }
            )
            position += 3 if command == ord("Q") else 2
        elif command in map(ord, "STVX"):
            position += 1
        elif command == ord("Y"):
            default_y = script[position]
            position += 1
        else:
            break
    if width_bytes <= 0 or height <= 0 or allocation_blocks <= 0:
        raise ValueError("ANM script is missing its A or B command")
    return width_bytes, height, allocation_blocks, references


def decode_odaanm(
    source: Path,
    output: Path,
    *,
    all_artifacts: bool = False,
) -> dict[str, object]:
    data = source.read_bytes()
    output.mkdir(parents=True, exist_ok=True)
    frames = []
    images = []
    sequences = []
    for sequence, script_offset in enumerate(ODAANM_SEQUENCE_OFFSETS):
        next_offset = (
            ODAANM_SEQUENCE_OFFSETS[sequence + 1]
            if sequence + 1 < len(ODAANM_SEQUENCE_OFFSETS)
            else len(data)
        )
        script = data[script_offset : script_offset + 0x100]
        width_bytes, height, allocation_blocks, references = parse_odaanm_script(script)
        width = width_bytes * 8
        frame_size = width_bytes * height * 3
        bank_offset = script_offset + 0x100
        bank = data[bank_offset:next_offset]

        unique_offsets = {}
        for reference in references:
            payload_in_bank = reference["block"] * 0x60
            payload_offset = bank_offset + payload_in_bank
            planar = bank[payload_in_bank : payload_in_bank + frame_size]
            if len(planar) != frame_size:
                raise EOFError(
                    f"ODAANM sequence {sequence}, block {reference['block']} is truncated"
                )
            digest = sha256(planar)
            if digest in unique_offsets:
                continue
            image, _pixels = decode_planar(planar, width, height)
            frame = save_frame(
                output,
                image,
                planar,
                payload_offset,
                relative_dir=Path(f"sequence_{sequence:02d}"),
                all_artifacts=all_artifacts,
            )
            frame.update(
                {
                    "sequence": sequence,
                    "block": reference["block"],
                }
            )
            frames.append(frame)
            images.append(image)
            unique_offsets[digest] = payload_offset
        sequences.append(
            {
                "sequence": sequence,
                "script_offset": hex_offset(script_offset),
                "width": width,
                "height": height,
                "allocation_blocks": allocation_blocks,
                "draw_commands": len(references),
                "unique_images": len(unique_offsets),
            }
        )
    if all_artifacts:
        save_sheet(images, output / "sheet.png")
    return finish_report(
        output,
        {
            "source": source.name,
            "source_sha256": sha256(data),
            "format": "256-byte command scripts plus interleaved B/R/G image banks",
            "sequences": sequences,
            "frames": frames,
        },
    )


def decode_fixed_frames(
    source: Path,
    output: Path,
    specs: tuple[tuple[int, int, int], ...],
    *,
    format_name: str,
    all_artifacts: bool = False,
) -> dict[str, object]:
    data = source.read_bytes()
    output.mkdir(parents=True, exist_ok=True)
    frames = []
    images = []
    for offset, width, height in specs:
        size = width // 8 * height * 3
        planar = data[offset : offset + size]
        if len(planar) != size:
            raise EOFError(f"{source.name}: frame at {hex_offset(offset)} is truncated")
        image, _pixels = decode_planar(planar, width, height)
        frames.append(
            save_frame(
                output,
                image,
                planar,
                offset,
                all_artifacts=all_artifacts,
            )
        )
        images.append(image)
    if all_artifacts:
        save_sheet(images, output / "sheet.png")
    return finish_report(
        output,
        {
            "source": source.name,
            "source_sha256": sha256(data),
            "format": format_name,
            "frames": frames,
        },
    )


def decode_hexmap(
    source: Path,
    output: Path,
) -> dict[str, object]:
    data = source.read_bytes()
    width, height = 55, 50
    pixels = data[: width * height]
    trailing = data[len(pixels) :]
    if len(pixels) != width * height or any(trailing):
        raise ValueError("HEXMAP.50 is not a padded 55x50-byte map")
    values = sorted(set(pixels))
    if len(values) > len(PC98_PALETTE_3BPP):
        raise ValueError("HEXMAP.50 has too many values for the diagnostic palette")
    colors = {value: PC98_PALETTE_3BPP[index] for index, value in enumerate(values)}
    image = Image.new("RGB", (width, height))
    image.putdata([colors[value] for value in pixels])
    image = image.resize((width * 8, height * 8), Image.Resampling.NEAREST)
    output.mkdir(parents=True, exist_ok=True)
    frame = save_frame(output, image, None, 0)
    return finish_report(
        output,
        {
            "source": source.name,
            "source_sha256": sha256(data),
            "format": "55x50 tile-index diagnostic map with zero padding",
            "trailing_bytes": len(trailing),
            "value_counts": {
                f"0x{value:02X}": count
                for value, count in sorted(Counter(pixels).items())
            },
            "frames": [frame],
        },
    )


def decode_all(workspace: ImageWorkspace, *, all_artifacts: bool = False) -> int:
    decode_odamain(
        workspace.source("ODAMAIN.EXE"),
        workspace.artifacts("ODAMAIN.EXE"),
        all_artifacts=all_artifacts,
    )
    decode_kao(
        workspace.source("KAO.DAT"),
        workspace.artifacts("KAO.DAT"),
        all_artifacts=all_artifacts,
    )
    decode_pak_container(
        workspace.source("MAP.DAT"),
        workspace.artifacts("MAP.DAT"),
        MAP_RECORDS,
        all_artifacts=all_artifacts,
    )
    decode_pak_container(
        workspace.source("HYOSI.DAT"),
        workspace.artifacts("HYOSI.DAT"),
        HYOSI_RECORDS,
        all_artifacts=all_artifacts,
    )
    decode_odaanm(
        workspace.source("ODAANM.DAT"),
        workspace.artifacts("ODAANM.DAT"),
        all_artifacts=all_artifacts,
    )
    decode_fixed_frames(
        workspace.source("SEISHIGA.DAT"),
        workspace.artifacts("SEISHIGA.DAT"),
        SEISHIGA_SPECS,
        format_name="four aligned raw interleaved B/R/G planar strips",
        all_artifacts=all_artifacts,
    )
    decode_fixed_frames(
        workspace.source("HATA.50"),
        workspace.artifacts("HATA.50"),
        tuple((index * 96, 16, 16) for index in range(57)),
        format_name="57 raw 16x16 interleaved B/R/G planar emblems",
        all_artifacts=all_artifacts,
    )
    decode_hexmap(
        workspace.source("HEXMAP.50"),
        workspace.artifacts("HEXMAP.50"),
    )
    return 8


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("c:/work_han/workspace0"),
        help=(
            "workspace containing jpn-pc98-384k and image-pc98-384k "
            "(default: c:/work_han/workspace0)"
        ),
    )
    parser.add_argument(
        "--all-artifacts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="also write compressed, planar, indexed, and contact-sheet artifacts",
    )
    args = parser.parse_args()
    workspace = ImageWorkspace(args.workspace, platform="pc98-384k")
    count = decode_all(workspace, all_artifacts=args.all_artifacts)
    print(f"decoded {count} source files into {workspace.image_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
