#!/usr/bin/env python3
"""Decode Necronomicon PC-98 GPC images and collect PNGs separately."""

from __future__ import annotations

import argparse
import json
import struct
from collections import Counter
from pathlib import Path

from PIL import Image

from gspecific.dob1.gpc import collect_gpc_output_modes
from module.pc98_image.formats.adv98_gpc import (
    GPCImage,
    decode_packed_palette_dac,
    undo_xor_delta as _runtime_undo_row,
    decode_gpc,
)
from module.pc98_image.indexed import IndexedImage
from module.pc98_image.pillow_adapter import to_pillow


KNOWN_OUTPUT_MODES = {
    # TITLE is the startup logo; mode 0 matches the captured PC-98 output.
    "TITLE.GPC": 0,
}
GPC_SIGNATURE = b"PC98)GPCFILE   \0"
VISIBLE_HEIGHTS = {
    # Legacy TMAST display correction; not yet verified against its runtime.
    "TMAST.GPC": 164,
}


def decode_necronomicon_gpc(data: bytes, *, output_mode: int = 0) -> GPCImage:
    """Select the shared codec's Necronomicon header and palette variant."""
    return decode_gpc(
        data, output_mode=output_mode, variant="necronomicon",
        palette_decoder=decode_packed_palette_dac,
        cumulative_xor=output_mode == 0,
    )


decode_necronomicon_runtime = decode_necronomicon_gpc


def write_artifacts(source: Path, workspace: Path, *, output_mode: int, observed_modes: dict[int, int]):
    data = source.read_bytes()
    decoded = decode_necronomicon_gpc(data, output_mode=output_mode)

    artifact_dir = workspace / "image-pc98" / "GPC"
    png_dir = workspace / "image-pc98" / "PNG"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)

    stem = source.stem
    (artifact_dir / f"{stem}.jpn{source.suffix}").write_bytes(data)
    (artifact_dir / f"{stem}.pln.jpn.bin").write_bytes(decoded.planar)
    (artifact_dir / f"{stem}.idx.jpn.bin").write_bytes(decoded.indices)

    image = IndexedImage.create(decoded.width, decoded.height, decoded.indices, decoded.palette)
    raw_png_path = png_dir / f"{stem}.raw.jpn.png"
    raw_image = to_pillow(image).convert("RGB")
    raw_image.save(raw_png_path)

    display_image = raw_image.copy()
    visible_height = VISIBLE_HEIGHTS.get(source.name.upper())
    if visible_height is not None and visible_height < display_image.height:
        display_image.paste(
            (0, 0, 0),
            (0, visible_height, display_image.width, display_image.height),
        )
    png_path = png_dir / f"{stem}.jpn.png"
    display_image.save(png_path)

    relative_source = source.relative_to(workspace / "jpn-pc98")
    metadata = {
        "source": str(relative_source).replace("\\", "/"),
        "offset": "0x000000",
        "original_size": decoded.source_size,
        "encoded_size": None,
        "stored_size": None,
        "padding_byte": None,
        "compression": "adv98-gpc-zero-mask-xor",
        "width": decoded.width,
        "height": decoded.height,
        "planes": decoded.descriptor_planes,
        "plane_order": "BRGI",
        "planar_layout": "row-major-plane-interlaced",
        "bit_order": "msb-first",
        "stride": (decoded.width + 7) // 8,
        "planar_segments": decoded.interlace,
        "palette": "embedded-0x0GRB",
        "palette_rgb_expansion": "6-bit-dac-bit-replication",
        "palette_offset": f"0x{decoded.palette_offset:06X}",
        "descriptor_offset": f"0x{decoded.descriptor_offset:06X}",
        "compressed_offset": f"0x{decoded.compressed_offset:06X}",
        "compressed_size": decoded.compressed_size,
        "compressed_consumed": decoded.compressed_consumed,
        "compressed_padding_size": decoded.compressed_padding_size,
        "display_x": decoded.x,
        "display_y": decoded.y,
        "descriptor_unknown_06": decoded.descriptor_unknown_06,
        "descriptor_flags": decoded.descriptor_flags,
        "output_mode": decoded.output_mode,
        "observed_output_modes": {
            str(mode): count for mode, count in sorted(observed_modes.items())
        },
        "png": str(png_path.relative_to(workspace)).replace("\\", "/"),
        "raw_png": str(raw_png_path.relative_to(workspace)).replace("\\", "/"),
        "visible_height": visible_height,
    }
    (artifact_dir / f"{stem}.meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return decoded, png_path


def embedded_gpc_ranges(data: bytes):
    """Yield ``(index, start, end)`` for GPC images embedded in a TCM."""
    start = 0
    index = 0
    while True:
        start = data.find(GPC_SIGNATURE, start)
        if start < 0:
            return
        if start + 0x20 > len(data):
            return
        descriptor_offset = struct.unpack_from("<I", data, start + 0x18)[0]
        descriptor = start + descriptor_offset
        if descriptor + 6 > len(data):
            start += len(GPC_SIGNATURE)
            continue
        stored_size = struct.unpack_from("<H", data, descriptor + 4)[0]
        # TCM-embedded GPC sizes exclude their 16-byte descriptor.
        end = descriptor + 0x10 + stored_size
        if end <= start or end > len(data):
            start += len(GPC_SIGNATURE)
            continue
        yield index, start, end
        index += 1
        start = end


def decode_tcm(source: Path, workspace: Path) -> int:
    """Extract embedded GPCs and write crop plus composited screen PNGs."""
    data = source.read_bytes()
    png_dir = workspace / "image-pc98" / "PNG"
    tcm_dir = workspace / "image-pc98" / "TCM"
    png_dir.mkdir(parents=True, exist_ok=True)
    tcm_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for index, start, end in embedded_gpc_ranges(data):
        decoded = decode_necronomicon_gpc(data[start:end], output_mode=1)
        image = IndexedImage.create(decoded.width, decoded.height, decoded.indices, decoded.palette)
        crop = to_pillow(image).convert("RGB")
        stem = f"{source.stem}.embedded-{index:03d}"
        crop_path = png_dir / f"{stem}.png"
        crop.save(crop_path)

        canvas_width = max(640, decoded.x + decoded.width)
        canvas_height = max(400, decoded.y + decoded.height)
        canvas = Image.new("RGB", (canvas_width, canvas_height), (0, 0, 0))
        canvas.paste(crop, (decoded.x, decoded.y))
        composite_path = png_dir / f"{source.stem}.composite-{index:03d}.png"
        canvas.save(composite_path)

        (tcm_dir / f"{stem}.GPC").write_bytes(data[start:end])
        metadata = {
            "source": str(source.relative_to(workspace / "jpn-pc98")).replace("\\", "/"),
            "embedded_index": index,
            "source_offset": f"0x{start:06X}",
            "source_end": f"0x{end:06X}",
            "width": decoded.width,
            "height": decoded.height,
            "display_x": decoded.x,
            "display_y": decoded.y,
            "output_mode": decoded.output_mode,
            "crop_png": str(crop_path.relative_to(workspace)).replace("\\", "/"),
            "composite_png": str(composite_path.relative_to(workspace)).replace("\\", "/"),
        }
        (tcm_dir / f"{stem}.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"{source.name}[{index}]: {decoded.width}x{decoded.height} "
            f"at ({decoded.x},{decoded.y}), composite={composite_path}"
        )
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(r"C:\work_han\workspace1"))
    parser.add_argument(
        "--file", action="append", dest="files",
        help="GPC filename; may be repeated (default: all GPC files)",
    )
    parser.add_argument(
        "--tcm-file", action="append", dest="tcm_files",
        help="TCM filename; may be repeated",
    )
    parser.add_argument(
        "--tcm-only", action="store_true",
        help="decode embedded GPC images from TCM files instead of standalone GPC files",
    )
    parser.add_argument("--mode", type=int, choices=(0, 1), help="force one GPC output mode")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    if args.tcm_only or args.tcm_files:
        tcm_root = workspace / "jpn-pc98" / "CMD"
        tcm_sources = sorted(tcm_root.glob("*.TCM"))
        if args.tcm_files:
            wanted = {name.upper() for name in args.tcm_files}
            tcm_sources = [source for source in tcm_sources if source.name.upper() in wanted]
        if not tcm_sources:
            raise FileNotFoundError(f"no requested TCM files found under {tcm_root}")
        total = sum(decode_tcm(source, workspace) for source in tcm_sources)
        print(f"decoded {total} embedded GPC image(s) from {len(tcm_sources)} TCM file(s)")
        if args.tcm_only:
            return 0

    source_root = workspace / "jpn-pc98" / "GPC"
    sources = sorted(source_root.glob("*.GPC"))
    if args.files:
        wanted = {name.upper() for name in args.files}
        sources = [source for source in sources if source.name.upper() in wanted]
    if not sources:
        return 0

    observed = collect_gpc_output_modes(workspace / "jpn-pc98" / "MES")
    failures = 0
    for source in sources:
        modes = observed.get(source.name.upper(), Counter())
        output_mode = args.mode
        if output_mode is None:
            output_mode = KNOWN_OUTPUT_MODES.get(
                source.name.upper(), modes.most_common(1)[0][0] if modes else 1
            )
        try:
            decoded, png_path = write_artifacts(
                source,
                workspace,
                output_mode=output_mode,
                observed_modes=dict(modes),
            )
        except (EOFError, ValueError, OSError) as error:
            failures += 1
            print(f"{source.name}: FAILED ({error})")
            continue
        print(
            f"{source.name}: {decoded.width}x{decoded.height}, "
            f"mode={decoded.output_mode}, compressed={decoded.compressed_size}, "
            f"png={png_path}"
        )
    if failures:
        print(f"completed with {failures} failed GPC file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
