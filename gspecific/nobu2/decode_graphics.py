#!/usr/bin/env python3
"""Decode Nobunaga Zenkokuban PC-98 graphics into workspace artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from PIL import Image

from gspecific.image_workspace import (
    ImageWorkspace,
    offset_stem,
    write_html_report,
)
from gspecific.nobu2.pc98_image_codec import decode_pak, decode_planar
from module.pc98_image.palette import PC98_PALETTE_3BPP

ODAMAIN_TABLE_OFFSET = 0x18650
ODAMAIN_RECORD_SIZE = 0x62
ODAMAIN_COUNT = 7

KAO_SPECS = {
    "MONTAGU.KAO": (0, 4, 64, 40),
    "BUSYOU.KAO": (0, 53, 64, 40),
    "HIME.KAO": (0, 20, 88, 48),
}

PAK_SPECS = {
    "ZENKOKU.PAK": (512, 160, 2, 2),
    "TOUHOKU.PAK": (512, 160, 2, 2),
    "HOKURIKU.PAK": (512, 160, 2, 2),
    "KANTOU.PAK": (512, 160, 2, 2),
    "TYUBU.PAK": (512, 160, 2, 2),
    "KINKI.PAK": (512, 160, 2, 2),
    "SHIKOKU.PAK": (512, 160, 2, 2),
    "KYUSYU.PAK": (512, 160, 2, 2),
    "MAP17.PAK": (512, 160, 2, 2),
    "TITLE.PAK": (640, 183, 4, 4),
    "END1.PAK": (640, 200, 2, 2),
    "END2.PAK": (640, 200, 2, 2),
}

MAP_PAK_NAMES = (
    "ZENKOKU.PAK",
    "TOUHOKU.PAK",
    "HOKURIKU.PAK",
    "KANTOU.PAK",
    "TYUBU.PAK",
    "KINKI.PAK",
    "SHIKOKU.PAK",
    "KYUSYU.PAK",
    "MAP17.PAK",
)

ODA98_SEQUENCE_OFFSETS = (
    0x00000,
    0x00C40,
    0x02CC0,
    0x040E0,
    0x05500,
    0x06380,
    0x077A0,
    0x08D40,
    0x09B60,
    0x0AF80,
    0x0BA40,
    0x0CE00,
    0x0E220,
    0x0F3A0,
    0x11480,
    0x12DE0,
    0x14860,
    0x16940,
    0x183C0,
    0x19E40,
    0x1BF20,
    0x1CC80,
    0x1DAA0,
    0x1FB80,
    0x20940,
    0x22A20,
    0x244A0,
    0x258C0,
)

SEISHIGA_SPECS = (
    (0x0000, 120, 32),
    (0x05A0, 136, 32),
    (0x0C00, 136, 32),
    (0x1260, 136, 32),
)


def hex_offset(value: int) -> str:
    return f"0x{value:06X}"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_frame(
    output: Path,
    image: Image.Image,
    planar: bytes | None,
    offset: int,
    *,
    relative_dir: Path = Path(),
    all_artifacts: bool = False,
) -> dict[str, object]:
    directory = output / relative_dir
    directory.mkdir(parents=True, exist_ok=True)
    stem = offset_stem(offset)
    png_name = f"{stem}.jpn.png"
    png_path = relative_dir / png_name
    image.save(output / png_path)
    files = {"png": png_path.as_posix()}
    if all_artifacts and planar is not None:
        planar_name = f"{stem}.pln.jpn.bin"
        planar_path = relative_dir / planar_name
        (output / planar_path).write_bytes(planar)
        files["planar"] = planar_path.as_posix()
    return {
        "offset": hex_offset(offset),
        "width": image.width,
        "height": image.height,
        "files": files,
    }


def save_sheet(
    images: list[Image.Image],
    path: Path,
    *,
    columns: int = 8,
    scale: int = 2,
) -> None:
    if not images:
        return
    cell_width = max(image.width for image in images)
    cell_height = max(image.height for image in images)
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (cell_width * columns, cell_height * rows),
        PC98_PALETTE_3BPP[0],
    )
    for index, image in enumerate(images):
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        sheet.paste(image.convert("RGB"), (x, y))
    if scale != 1:
        sheet = sheet.resize(
            (sheet.width * scale, sheet.height * scale),
            Image.Resampling.NEAREST,
        )
    sheet.save(path)


def finish_report(output: Path, report: dict[str, object]) -> dict[str, object]:
    (output / "log.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\r\n",
    )
    write_html_report(report, output)
    return report


def decode_fixed_frames(
    source: Path,
    output: Path,
    specs: list[tuple[int, int, int]],
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
    consumed_size = max(
        (offset + width // 8 * height * 3 for offset, width, height in specs),
        default=0,
    )
    return finish_report(
        output,
        {
            "source": source.name,
            "source_sha256": sha256(data),
            "format": format_name,
            "consumed_size": consumed_size,
            "trailing_bytes": len(data) - consumed_size,
            "frames": frames,
        },
    )


def decode_kao(
    source: Path,
    output: Path,
    skip: int,
    count: int,
    width: int,
    height: int,
    *,
    all_artifacts: bool = False,
) -> dict[str, object]:
    frame_size = width // 8 * height * 3
    specs = [(skip + index * frame_size, width, height) for index in range(count)]
    report = decode_fixed_frames(
        source,
        output,
        specs,
        format_name=f"{width}x{height} interleaved B/R/G planar portraits",
        all_artifacts=all_artifacts,
    )
    report["frame_size"] = frame_size
    report["trailing_bytes"] = source.stat().st_size - (skip + count * frame_size)
    return finish_report(output, report)


def decode_pak_file(
    source: Path,
    output: Path,
    width: int,
    height: int,
    literal_rows: int,
    copy_rows: int,
    *,
    all_artifacts: bool = False,
    write_report: bool = True,
) -> dict[str, object]:
    data = source.read_bytes()
    image, planar, _pixels, info = decode_pak(data, width, height, literal_rows, copy_rows)
    output.mkdir(parents=True, exist_ok=True)
    stem = source.stem
    png_name = f"{stem}.jpn.png"
    image.save(output / png_name)
    frame = {
        "offset": hex_offset(0),
        "width": width,
        "height": height,
        "files": {"png": png_name},
    }
    if all_artifacts:
        planar_name = f"{stem}.pln.jpn.bin"
        native_name = f"{stem}.jpn{source.suffix}"
        (output / planar_name).write_bytes(planar)
        (output / native_name).write_bytes(data)
        frame["files"].update({"planar": planar_name, "compressed": native_name})
    report = {
        "source": source.name,
        "source_sha256": sha256(data),
        "format": "Nobu2 0x96 vertical-copy PAK",
        **info,
        "frames": [frame],
    }
    return finish_report(output, report) if write_report else report


def decode_map_paks(
    workspace: ImageWorkspace,
    *,
    all_artifacts: bool = False,
) -> dict[str, object]:
    output = workspace.artifacts("MAP")
    frames = []
    sources = []
    for name in MAP_PAK_NAMES:
        width, height, literal_rows, copy_rows = PAK_SPECS[name]
        report = decode_pak_file(
            workspace.source(name),
            output,
            width,
            height,
            literal_rows,
            copy_rows,
            all_artifacts=all_artifacts,
            write_report=False,
        )
        frame = report["frames"][0]
        frame["source"] = name
        frames.append(frame)
        sources.append(
            {
                "source": name,
                "source_sha256": report["source_sha256"],
                "compressed_size": report["compressed_size"],
                "padding_size": report["padding_size"],
            }
        )
    return finish_report(
        output,
        {
            "source": "Nobu2 map PAK files",
            "format": "Nobu2 0x96 vertical-copy PAK",
            "sources": sources,
            "frames": frames,
        },
    )


def decode_odamain(
    source: Path,
    output: Path,
    *,
    all_artifacts: bool = False,
) -> dict[str, object]:
    data = source.read_bytes()
    required = ODAMAIN_TABLE_OFFSET + ODAMAIN_COUNT * ODAMAIN_RECORD_SIZE
    if data[:2] != b"MZ" or len(data) < required:
        raise ValueError("unsupported or truncated ODAMAIN.EXE")
    output.mkdir(parents=True, exist_ok=True)
    frames = []
    images = []
    for index in range(ODAMAIN_COUNT):
        record_offset = ODAMAIN_TABLE_OFFSET + index * ODAMAIN_RECORD_SIZE
        x_byte, screen_y = data[record_offset : record_offset + 2]
        payload_offset = record_offset + 2
        planar = data[payload_offset : payload_offset + 2 * 8 * 3]
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


def parse_oda98_script(
    script: bytes,
) -> tuple[int, int, int, list[dict[str, int]]]:
    position = 0
    width_bytes = height = bank_blocks = -1
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
            bank_blocks = script[position]
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
        elif command in map(ord, "TVX"):
            position += 1
        elif command == ord("Y"):
            default_y = script[position]
            position += 1
        else:
            break
    if width_bytes <= 0 or height <= 0 or bank_blocks <= 0:
        raise ValueError("ANM script is missing its A or B command")
    return width_bytes, height, bank_blocks, references


def decode_oda98(
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
    for sequence, script_offset in enumerate(ODA98_SEQUENCE_OFFSETS):
        script = data[script_offset : script_offset + 0x100]
        if len(script) != 0x100:
            raise EOFError(f"ODA98 sequence {sequence} has a truncated script")
        width_bytes, height, bank_blocks, references = parse_oda98_script(script)
        width = width_bytes * 8
        frame_size = width_bytes * height * 3
        bank_offset = script_offset + 0x100
        bank_size = bank_blocks * 0x100
        bank = data[bank_offset : bank_offset + bank_size]
        if len(bank) != bank_size:
            raise EOFError(f"ODA98 sequence {sequence} has a truncated bank")

        unique_offsets = {}
        sequence_frames = 0
        for reference in references:
            payload_in_bank = reference["block"] * 0x60
            payload_offset = bank_offset + payload_in_bank
            planar = bank[payload_in_bank : payload_in_bank + frame_size]
            if len(planar) != frame_size:
                raise EOFError(f"ODA98 sequence {sequence}, block {reference['block']} is truncated")
            digest = sha256(planar)
            if digest not in unique_offsets:
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
            sequence_frames += 1
        sequences.append(
            {
                "sequence": sequence,
                "script_offset": hex_offset(script_offset),
                "width": width,
                "height": height,
                "bank_blocks": bank_blocks,
                "draw_commands": sequence_frames,
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


def decode_hexmap(
    source: Path,
    output: Path,
    *,
    all_artifacts: bool = False,
) -> dict[str, object]:
    del all_artifacts
    data = source.read_bytes()
    width, height = 55, 50
    if len(data) != width * height:
        raise ValueError("HEXMAP.50 is not the expected 55x50-byte map")
    values = sorted(set(data))
    if len(values) > len(PC98_PALETTE_3BPP):
        raise ValueError("HEXMAP.50 has too many values for the diagnostic palette")
    colors = {value: PC98_PALETTE_3BPP[index] for index, value in enumerate(values)}
    image = Image.new("RGB", (width, height))
    image.putdata([colors[value] for value in data])
    image = image.resize((width * 8, height * 8), Image.Resampling.NEAREST)
    output.mkdir(parents=True, exist_ok=True)
    frame = save_frame(output, image, None, 0)
    return finish_report(
        output,
        {
            "source": source.name,
            "source_sha256": sha256(data),
            "format": "55x50 tile-index diagnostic map (not planar pixels)",
            "value_counts": {f"0x{value:02X}": count for value, count in sorted(Counter(data).items())},
            "frames": [frame],
        },
    )


def decode_all(workspace: ImageWorkspace, *, all_artifacts: bool = False) -> int:
    jobs = 0
    decode_odamain(
        workspace.source("ODAMAIN.EXE"),
        workspace.artifacts("ODAMAIN.EXE"),
        all_artifacts=all_artifacts,
    )
    jobs += 1
    for name, (skip, count, width, height) in KAO_SPECS.items():
        decode_kao(
            workspace.source(name),
            workspace.artifacts(name),
            skip,
            count,
            width,
            height,
            all_artifacts=all_artifacts,
        )
        jobs += 1
    for name, (width, height, literal_rows, copy_rows) in PAK_SPECS.items():
        if name in MAP_PAK_NAMES:
            continue
        decode_pak_file(
            workspace.source(name),
            workspace.artifacts(name),
            width,
            height,
            literal_rows,
            copy_rows,
            all_artifacts=all_artifacts,
        )
        jobs += 1
    decode_map_paks(workspace, all_artifacts=all_artifacts)
    jobs += len(MAP_PAK_NAMES)
    decode_oda98(
        workspace.source("ODA98.ANM"),
        workspace.artifacts("ODA98.ANM"),
        all_artifacts=all_artifacts,
    )
    jobs += 1
    decode_fixed_frames(
        workspace.source("SEISHIGA.ANM"),
        workspace.artifacts("SEISHIGA.ANM"),
        list(SEISHIGA_SPECS),
        format_name="four raw interleaved B/R/G planar strips",
        all_artifacts=all_artifacts,
    )
    jobs += 1
    decode_fixed_frames(
        workspace.source("HATA.50"),
        workspace.artifacts("HATA.50"),
        [(index * 96, 16, 16) for index in range(57)],
        format_name="57 raw 16x16 interleaved B/R/G planar emblems",
        all_artifacts=all_artifacts,
    )
    jobs += 1
    decode_fixed_frames(
        workspace.source("HPUT.DAT"),
        workspace.artifacts("HPUT.DAT"),
        [(index * 576, 48, 32) for index in range(6)],
        format_name="six raw 48x32 interleaved B/R/G planar terrain tiles",
        all_artifacts=all_artifacts,
    )
    jobs += 1
    decode_hexmap(
        workspace.source("HEXMAP.50"),
        workspace.artifacts("HEXMAP.50"),
        all_artifacts=all_artifacts,
    )
    return jobs + 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("c:/work_han/workspace"),
        help="workspace containing jpn-pc98 and image-pc98 (default: c:/work_han/workspace)",
    )
    parser.add_argument(
        "--all-artifacts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="also write planar binaries and contact sheets (default: disabled)",
    )
    args = parser.parse_args()
    count = decode_all(ImageWorkspace(args.workspace), all_artifacts=args.all_artifacts)
    print(f"decoded {count} source files into {args.workspace / 'image-pc98'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
