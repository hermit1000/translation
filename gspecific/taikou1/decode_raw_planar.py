#!/usr/bin/env python3
"""Decode fixed-size raw planar archives into workspace artifacts."""

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from gspecific.image_workspace import (
    ImageWorkspace,
    offset_stem,
    update_meta,
    write_html_report,
)
from gspecific.taikou1.pc98_image_codec import decode_planar

JOBS = (
    # ("ANIME.PUT", 16, 16, 3),
    ("GRAPH.PUT", 32, 32, 3),
    # ("HEX.PUT", 40, 24, 3),
    ("HIME.PUT", 64, 80, 3),
    ("KAO.PUT", 64, 80, 3),
    # ("MONTA.PUT", 48, 24, 4),
    # ("SAIKORO.PUT", 24, 18, 4),
    # ("UNIT.PUT", 16, 16, 3),
    ("PTN.DAT", 32, 32, 3),
)

FRAME_OVERRIDES = {
    "GRAPH.PUT": {
        0x000180: (64, 48, 3),
    },
}

EMBEDDED_JOBS = (
    (
        "MAIN.EXE",
        ((0x060B90, 32, 32, 3),),
    ),
)


def hex_offset(value):
    return f"0x{value:06X}"


def decode_block(data, offset, width, height, planes):
    if width % 8:
        raise ValueError("width must be divisible by 8")
    size = width * height * planes // 8
    if offset + size > len(data):
        raise EOFError("incomplete PUT block")

    image, _ = decode_planar(data[offset : offset + size], width, height, planes)
    return image, size


def frame_layout(data_size, width, height, planes, overrides=None):
    """Yield mixed-size raw planar frame boundaries, applying offset overrides."""
    overrides = overrides or {}
    offset = 0
    while offset < data_size:
        frame_width, frame_height, frame_planes = overrides.get(offset, (width, height, planes))
        frame_size = frame_width * frame_height * frame_planes // 8
        if offset + frame_size > data_size:
            break
        yield offset, frame_width, frame_height, frame_planes, frame_size
        offset += frame_size


def decode_file(
    source,
    output_dir,
    width,
    height,
    planes,
    columns=16,
    scale=1,
    *,
    frame_overrides=None,
    frame_ranges=None,
    source_label=None,
    all_artifacts=False,
):
    source = Path(source)
    data = source.read_bytes()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    block_size = width * height * planes // 8
    if frame_ranges is None:
        layout = list(frame_layout(len(data), width, height, planes, frame_overrides))
    else:
        layout = [
            (
                offset,
                frame_width,
                frame_height,
                frame_planes,
                frame_width * frame_height * frame_planes // 8,
            )
            for offset, frame_width, frame_height, frame_planes in frame_ranges
        ]
        for offset, _width, _height, _planes, frame_size in layout:
            if offset + frame_size > len(data):
                raise EOFError(f"frame at 0x{offset:06X} extends past {source} EOF")
    count = len(layout)
    consumed = layout[-1][0] + layout[-1][4] if layout else 0
    remainder = 0 if frame_ranges is not None else len(data) - consumed
    sheet_frames = []
    report_frames = []
    for index, (offset, frame_width, frame_height, frame_planes, frame_size) in enumerate(layout):
        next_offset = offset + frame_size
        stem = offset_stem(offset)
        planar = data[offset:next_offset]
        image, pixels = decode_planar(planar, frame_width, frame_height, frame_planes)
        plane_name = f"{stem}.pln.jpn.bin"
        pixels_name = f"{stem}.idx.jpn.bin"
        png_name = f"{stem}.jpn.png"
        if all_artifacts:
            (output / plane_name).write_bytes(planar)
            (output / pixels_name).write_bytes(pixels)
        image.save(output / png_name)
        if all_artifacts:
            update_meta(
                output / f"{stem}.meta.json",
                source=str(source_label or source),
                offset=hex_offset(offset),
                original_size=frame_size,
                encoded_size=None,
                stored_size=None,
                padding_byte=None,
                compression="none",
                width=frame_width,
                height=frame_height,
                planes=frame_planes,
                plane_order="BRG" if frame_planes == 3 else "BRGI",
                planar_layout="interleaved",
                bit_order="msb-first",
                stride=frame_width // 8 * frame_planes,
                palette="pc98-8color" if frame_planes == 3 else "pc98-16color",
            )
            sheet_frames.append(image.convert("RGB"))
        files = {"png": png_name}
        if all_artifacts:
            files = {
                "plane": plane_name,
                "pixels": pixels_name,
                **files,
            }
        report_frames.append(
            {
                "index": index,
                "offset": hex_offset(offset),
                "next_offset": hex_offset(next_offset),
                "plane_size": frame_size,
                "width": frame_width,
                "height": frame_height,
                "planes": frame_planes,
                "files": files,
            }
        )

    if all_artifacts and sheet_frames:
        rows = math.ceil(count / columns)
        label_height = 10
        max_width = max(image.width for image in sheet_frames)
        max_height = max(image.height for image in sheet_frames)
        cell_width = max_width * scale
        cell_height = max_height * scale + label_height
        sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), (32, 32, 32))
        draw = ImageDraw.Draw(sheet)
        for index, image in enumerate(sheet_frames):
            x = (index % columns) * cell_width
            y = (index // columns) * cell_height
            if scale != 1:
                image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
            image_x = x + (cell_width - image.width) // 2
            sheet.paste(image, (image_x, y))
            draw.text((x, y + max_height * scale), str(index), fill=(255, 255, 255))
        sheet.save(output / "sheet.png")

    report = {
        "source": str(source),
        "format": f"raw {planes}bpp planar B/R/G" + ("/I" if planes == 4 else ""),
        "block_size": block_size,
        "frames": report_frames,
    }
    if remainder:
        report["incomplete"] = {
            "offset": hex_offset(consumed),
            "remaining_bytes": remainder,
        }
    (output / "log.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\r\n",
    )
    write_html_report(report, output)
    return count, remainder, block_size


def main():
    parser = argparse.ArgumentParser(description="Decode fixed-size raw planar archives")
    parser.add_argument(
        "--workspace",
        default=Path("c:/work_han/workspace"),
        type=Path,
        help="workspace containing jpn-pc98 and image-pc98 (default: c:/work_han/workspace)",
    )
    parser.add_argument(
        "--all-artifacts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="write intermediate binaries, metadata, and contact sheet (default: disabled)",
    )
    args = parser.parse_args()
    workspace = ImageWorkspace(args.workspace)
    for relative_source, width, height, planes in JOBS:
        source = workspace.source(relative_source)
        output_dir = workspace.artifacts(relative_source)
        frame_overrides = FRAME_OVERRIDES.get(relative_source)
        count, remainder, block_size = decode_file(
            source,
            output_dir,
            width,
            height,
            planes,
            frame_overrides=frame_overrides,
            source_label=relative_source,
            all_artifacts=args.all_artifacts,
        )
        print(f"{source}: decoded={count} remainder={remainder} block_size={block_size} output={output_dir}")
    for relative_source, frame_ranges in EMBEDDED_JOBS:
        source = workspace.source(relative_source)
        output_dir = workspace.artifacts(relative_source)
        width, height, planes = frame_ranges[0][1:]
        count, remainder, block_size = decode_file(
            source,
            output_dir,
            width,
            height,
            planes,
            frame_ranges=frame_ranges,
            source_label=relative_source,
            all_artifacts=args.all_artifacts,
        )
        print(f"{source}: decoded={count} embedded frame(s) block_size={block_size} output={output_dir}")


if __name__ == "__main__":
    main()
