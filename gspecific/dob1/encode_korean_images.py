"""Encode all Korean FRR/BLTY PNGs as ADV98 GPC files."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from PIL import Image

from module.pc98_image.adv98_artifacts import normalize_indexed
from module.pc98_image.formats.adv98_gpc import (
    PLANES, decode_gpc, encode_gpc, encode_gpc as encode_standard_gpc,
    indices_to_logical_rows, inverse_vertical_xor, inverse_horizontal_xor,
    pack_zero_masks, unpack_zero_masks,
)


def encode_frr(source_gpc: bytes, indices: bytes, *, runtime_compatibility: bool = True) -> tuple[bytes, bytes]:
    """Use the shared codec, retaining DOB1's explicit legacy FRR option."""
    decoded = decode_gpc(source_gpc, output_mode=0)
    if decoded.width != 640 or decoded.height != 400 or decoded.interlace != 2:
        raise ValueError("FRR encoder expects a 640x400, interlace-2 GPC")
    encoded, planar = encode_gpc(source_gpc, indices, output_mode=0)
    if not runtime_compatibility:
        return encoded, planar
    clean = decode_gpc(encoded, output_mode=0)
    row_size = 1 + ((clean.width + 7) // 8) * PLANES
    expanded, _ = unpack_zero_masks(
        encoded[clean.compressed_offset:clean.compressed_offset + clean.compressed_size],
        row_size * clean.height,
    )
    expanded = bytearray(expanded)
    # Preserve the existing game-specific option; not part of the codec.
    expanded[299 * row_size + 2] ^= 0x20
    expanded += bytes(-len(expanded) % 64)
    compressed = pack_zero_masks(expanded)
    if len(compressed) > 0xFFFF:
        raise ValueError("encoded FRR compressed stream exceeds 65535 bytes")
    output = bytearray(encoded[:clean.compressed_offset])
    output.extend(compressed)
    output.extend(encoded[clean.compressed_offset + clean.compressed_size:])
    struct.pack_into("<H", output, clean.descriptor_offset + 4, len(compressed))
    struct.pack_into("<I", output, 0x20, len(output))
    return bytes(output), planar


def encode_blty_part(
    workspace: Path,
    input_dir: Path,
    name: str,
    output_mode: int,
) -> None:
    source_path = workspace / "jpn-pc98" / "GRAPH" / f"{name}.GPC"
    reference_path = input_dir / "BLTY_AB.jpn.png"
    png_path = input_dir / f"{name}.kor.png"
    output_path = input_dir / f"{name}.kor.GPC"

    source = source_path.read_bytes()
    indexed = normalize_indexed(Image.open(png_path), Image.open(reference_path))
    indices = bytes(indexed.getdata())
    encoded, planar = encode_standard_gpc(
        source, indices, output_mode=output_mode
    )
    verification = decode_gpc(encoded, output_mode=output_mode)
    if verification.indices != indices:
        raise ValueError(f"{name} encoding does not round-trip")

    output_path.write_bytes(encoded)
    (input_dir / f"{name}.idx.kor.bin").write_bytes(indices)
    (input_dir / f"{name}.pln.kor.bin").write_bytes(planar)
    metadata = {
        "source": f"jpn-pc98/GRAPH/{name}.GPC",
        "input": f"binary_inputs-pc98/{name}.kor.png",
        "output": f"binary_inputs-pc98/{name}.kor.GPC",
        "width": verification.width,
        "height": verification.height,
        "display_x": verification.x,
        "display_y": verification.y,
        "interlace": verification.interlace,
        "output_mode": output_mode,
        "compressed_size": verification.compressed_size,
        "file_size": len(encoded),
        "roundtrip_index_match": True,
    }
    (input_dir / f"{name}.kor.meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{name} encode: {png_path} -> {output_path}, "
        f"mode={output_mode}, compressed={verification.compressed_size}, "
        f"file={len(encoded)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    input_dir = workspace / "binary_inputs-pc98"
    source_path = workspace / "jpn-pc98" / "GRAPH" / "FRR.GPC"
    reference_path = workspace / "image-pc98" / "GRAPH" / "FRR.GPC" / "FRR.jpn.png"
    png_path = input_dir / "FRR.kor.png"
    output_path = input_dir / "FRR.kor.GPC"

    source = source_path.read_bytes()
    indexed = normalize_indexed(Image.open(png_path), Image.open(reference_path))
    indices = bytes(indexed.getdata())
    clean_encoded, planar = encode_frr(
        source, indices, runtime_compatibility=False
    )
    clean_verification = decode_gpc(clean_encoded, output_mode=0)
    if clean_verification.indices != indices:
        raise ValueError("clean FRR encoding does not round-trip to the input indices")

    encoded, _ = encode_frr(source, indices, runtime_compatibility=True)

    verification = decode_gpc(encoded, output_mode=0)

    output_path.write_bytes(encoded)
    (input_dir / "FRR.idx.kor.bin").write_bytes(indices)
    (input_dir / "FRR.pln.kor.bin").write_bytes(planar)
    metadata = {
        "source": "jpn-pc98/GRAPH/FRR.GPC",
        "input": "binary_inputs-pc98/FRR.kor.png",
        "output": "binary_inputs-pc98/FRR.kor.GPC",
        "width": verification.width,
        "height": verification.height,
        "planes": verification.descriptor_planes,
        "plane_order": "BRGI",
        "interlace": verification.interlace,
        "output_mode": 0,
        "compressed_size": verification.compressed_size,
        "file_size": len(encoded),
        "roundtrip_index_match_before_runtime_compatibility": True,
        "runtime_compatibility": "ADV98 FRR row-299 byte-2 xor 0x20",
    }
    (input_dir / "FRR.kor.meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"FRR encode: {png_path} -> {output_path}, "
        f"compressed={verification.compressed_size}, file={len(encoded)}"
    )

    encode_blty_part(workspace, input_dir, "BLTY_A", output_mode=0)
    encode_blty_part(workspace, input_dir, "BLTY_B", output_mode=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
