#!/usr/bin/env python3
"""Decode the game's RLE/LZ image archives into workspace artifacts."""

import argparse
import json
from pathlib import Path

from gspecific.image_workspace import (
    ImageWorkspace,
    offset_stem,
    update_meta,
    write_html_report,
)
from gspecific.taikou1.pc98_image_codec import decode_rle_lz


JOBS = (
    ("OPEN.DAT", False),
    ("END.DAT", True),
    ("GRAPH.DAT", False),
    ("EV_PIC.DAT", False),
    # ("INT_BAK.NPK", False),
)


def hex_offset(value):
    return f"0x{value:06X}"


def decode_file(
    source,
    output_dir,
    *,
    offset_names=False,
    allow_incomplete=False,
    source_label=None,
    all_artifacts=False,
):
    data = Path(source).read_bytes()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    frames = []
    incomplete = None
    offset = 0
    while offset < len(data):
        try:
            image, _planar, pixels, info = decode_rle_lz(data, offset)
        except EOFError as error:
            if not allow_incomplete:
                raise
            incomplete = {
                "offset": offset,
                "remaining_bytes": len(data) - offset,
                "error": str(error),
            }
            break
        index = len(frames)
        stem = offset_stem(offset) if offset_names else f"{index:03d}_{offset_stem(offset)}"
        compressed = data[offset : info["next_offset"]]
        compressed_name = f"{stem}.cmp.jpn.bin"
        pixels_name = f"{stem}.idx.jpn.bin"
        png_name = f"{stem}.jpn.png"
        if all_artifacts:
            (output / compressed_name).write_bytes(compressed)
            (output / pixels_name).write_bytes(pixels)
        image.save(output / png_name)
        if all_artifacts:
            update_meta(
                output / f"{stem}.meta.json",
                source=str(source_label or source),
                offset=hex_offset(info["offset"]),
                original_size=info["compressed_size"],
                encoded_size=None,
                stored_size=None,
                padding_byte=None,
                compression="taikou1-rle-lz",
                width=info["width"],
                height=info["height"],
                planes=3,
                plane_order="BRG",
                planar_layout=None,
                bit_order="msb-first",
                stride=None,
                palette="pc98-8color",
            )
        info["files"] = {"png": png_name}
        if all_artifacts:
            info["files"] = {
                "compressed": compressed_name,
                "pixels": pixels_name,
                **info["files"],
            }
        frames.append(info)
        offset = info["next_offset"]
    report_frames = []
    for frame in frames:
        report_frame = dict(frame)
        report_frame["offset"] = hex_offset(frame["offset"])
        report_frame["next_offset"] = hex_offset(frame["next_offset"])
        report_frames.append(report_frame)
    report = {"source": str(source), "frames": report_frames}
    if incomplete:
        report["incomplete"] = {
            **incomplete,
            "offset": hex_offset(incomplete["offset"]),
        }
    (output / "log.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\r\n",
    )
    write_html_report(report, output)
    return frames


def main():
    parser = argparse.ArgumentParser(
        description="Decode the game's RLE/LZ image archives"
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
        help="write intermediate binaries and metadata (default: disabled)",
    )
    args = parser.parse_args()
    workspace = ImageWorkspace(args.workspace)
    for relative_source, allow_incomplete in JOBS:
        source = workspace.source(relative_source)
        output_dir = workspace.artifacts(relative_source)
        frames = decode_file(
            source,
            output_dir,
            offset_names=True,
            allow_incomplete=allow_incomplete,
            source_label=relative_source,
            all_artifacts=args.all_artifacts,
        )
        print(f"{source}: decoded={len(frames)} output={output_dir}")


if __name__ == "__main__":
    main()
