#!/usr/bin/env python3
"""Encode workspace *.kor.png files as raw planar blocks."""

import argparse
import json
from pathlib import Path

from gspecific.image_workspace import ImageWorkspace, update_meta
from gspecific.taikou1.decode_raw_planar import (
    EMBEDDED_JOBS,
    FRAME_OVERRIDES,
    JOBS,
    frame_layout,
)
from gspecific.taikou1.pc98_image_codec import image_to_planar


def hex_offset(value):
    return f"0x{value:06X}"


def offset_pngs(directory):
    for path in sorted(directory.glob("*.kor.png")):
        try:
            offset = int(path.name.removesuffix(".kor.png"), 16)
        except ValueError:
            continue
        yield offset, path


def encode_folder(
    source,
    artifact_dir,
    width,
    height,
    planes,
    *,
    frame_overrides=None,
    frame_ranges=None,
    all_artifacts=False,
):
    artifact_dir = Path(artifact_dir)
    if not artifact_dir.is_dir():
        print(f"skip: {artifact_dir} does not exist")
        return 0

    source_path = Path(source)
    source_size = source_path.stat().st_size
    block_size = width * height * planes // 8
    if frame_ranges is None:
        layout = {
            offset: (frame_width, frame_height, frame_planes, frame_size)
            for offset, frame_width, frame_height, frame_planes, frame_size in frame_layout(
                source_size, width, height, planes, frame_overrides
            )
        }
    else:
        layout = {
            offset: (
                frame_width,
                frame_height,
                frame_planes,
                frame_width * frame_height * frame_planes // 8,
            )
            for offset, frame_width, frame_height, frame_planes in frame_ranges
        }
    entries = []
    for offset, png_path in offset_pngs(artifact_dir):
        if offset not in layout:
            raise ValueError(f"{png_path}: offset is not a known frame boundary")
        frame_width, frame_height, frame_planes, frame_size = layout[offset]

        encoded, _pixels = image_to_planar(
            png_path, frame_width, frame_height, frame_planes
        )
        stem = f"{offset:06X}"
        output_name = f"{stem}.pln.kor.bin"
        (artifact_dir / output_name).write_bytes(encoded)
        if all_artifacts:
            update_meta(
                artifact_dir / f"{stem}.meta.json",
                encoded_size=len(encoded),
                stored_size=len(encoded),
                padding_byte=None,
            )
        entries.append(
            {
                "offset": hex_offset(offset),
                "next_offset": hex_offset(offset + frame_size),
                "width": frame_width,
                "height": frame_height,
                "planes": frame_planes,
                "encoded_size": len(encoded),
                "files": {"png": png_path.name, "encoded": output_name},
            }
        )
        print(f"{png_path}: encoded={len(encoded)}")

    report = {
        "source": str(source_path),
        "format": f"raw {planes}bpp planar B/R/G" + ("/I" if planes == 4 else ""),
        "block_size": block_size,
        "entries": entries,
    }
    (artifact_dir / "log.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\r\n",
    )
    print(f"{artifact_dir}: encoded={len(entries)}")
    return len(entries)


def main():
    parser = argparse.ArgumentParser(
        description="Encode workspace *.kor.png files as raw planar blocks"
    )
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
        help="write per-frame metadata files (default: disabled)",
    )
    args = parser.parse_args()
    workspace = ImageWorkspace(args.workspace)
    for relative_source, width, height, planes in JOBS:
        source = workspace.source(relative_source)
        artifact_dir = workspace.artifacts(relative_source)
        encode_folder(
            source,
            artifact_dir,
            width,
            height,
            planes,
            frame_overrides=FRAME_OVERRIDES.get(relative_source),
            all_artifacts=args.all_artifacts,
        )
    for relative_source, frame_ranges in EMBEDDED_JOBS:
        source = workspace.source(relative_source)
        artifact_dir = workspace.artifacts(relative_source)
        width, height, planes = frame_ranges[0][1:]
        encode_folder(
            source,
            artifact_dir,
            width,
            height,
            planes,
            frame_ranges=frame_ranges,
            all_artifacts=args.all_artifacts,
        )


if __name__ == "__main__":
    main()
