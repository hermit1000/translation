"""Encode all Korean FRR/BLTY PNGs as ADV98 GPC files."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from PIL import Image

from gspecific.dob1.gpc import PLANES, decode_gpc, pack_zero_masks, unpack_zero_masks


def normalize_indexed(image: Image.Image, reference: Image.Image) -> Image.Image:
    """Return an indexed copy using the reference's exact 16-color palette."""
    if image.mode == "P":
        return image.copy()
    if reference.mode != "P":
        raise ValueError("palette reference must be an indexed PNG")
    palette = reference.getpalette()
    color_to_index = {
        tuple(palette[index * 3 : index * 3 + 3]): index for index in range(16)
    }
    rgb = image.convert("RGB")
    indices = []
    for color in rgb.getdata():
        if color not in color_to_index:
            raise ValueError(f"image contains an unknown palette color {color}")
        indices.append(color_to_index[color])
    indexed = Image.new("P", image.size)
    indexed.putpalette(palette)
    indexed.putdata(indices)
    return indexed


def indices_to_logical_rows(indices: bytes, width: int, height: int) -> list[bytes]:
    stride = (width + 7) // 8
    rows = []
    for y in range(height):
        row = bytearray(stride * PLANES)
        for x in range(width):
            value = indices[y * width + x]
            byte_index = x // 8
            bit = 0x80 >> (x % 8)
            for plane in range(PLANES):
                if value & (1 << plane):
                    row[plane * stride + byte_index] |= bit
        rows.append(bytes(row))
    return rows


def inverse_vertical_xor(rows: list[bytes]) -> list[bytes]:
    encoded = []
    previous = None
    for row in rows:
        if previous is None:
            encoded.append(row)
        else:
            encoded.append(bytes(a ^ b for a, b in zip(row, previous)))
        previous = row
    return encoded


def inverse_horizontal_xor(row: bytes, stride: int) -> bytes:
    if stride == 0:
        return row
    encoded = bytearray(row)
    for offset in range(len(row) - 1, stride - 1, -1):
        encoded[offset] ^= row[offset - stride]
    return bytes(encoded)


def encode_frr(
    source_gpc: bytes,
    indices: bytes,
    *,
    runtime_compatibility: bool = True,
) -> tuple[bytes, bytes]:
    decoded = decode_gpc(source_gpc, output_mode=0)
    if decoded.width != 640 or decoded.height != 400 or decoded.interlace != 2:
        raise ValueError("FRR encoder expects a 640x400, interlace-2 GPC")
    if len(indices) != decoded.width * decoded.height:
        raise ValueError("FRR indexed image has an invalid size")
    if max(indices) >= 16:
        raise ValueError("FRR indexed image contains a palette index above 15")

    logical_rows = indices_to_logical_rows(indices, decoded.width, decoded.height)
    stream_rows = [
        logical_rows[y]
        for first_y in range(decoded.interlace)
        for y in range(first_y, decoded.height, decoded.interlace)
    ]
    vertical_rows = inverse_vertical_xor(stream_rows)

    row_size = 1 + len(stream_rows[0])
    original_expanded, _ = unpack_zero_masks(
        source_gpc[
            decoded.compressed_offset : decoded.compressed_offset
            + decoded.compressed_size
        ],
        row_size * decoded.height,
    )
    original_strides = original_expanded[::row_size]
    expanded = bytearray().join(
        bytes((stride,)) + inverse_horizontal_xor(row, stride)
        for row, stride in zip(vertical_rows, original_strides)
    )
    if runtime_compatibility:
        # ADV98's buffered decoder toggles this bit at the row-299 boundary.
        # The original FRR contains the inverse bit and therefore renders clean
        # in the game even though a whole-stream decoder shows stripes.
        expanded[299 * row_size + 2] ^= 0x20
    expanded += bytes(-len(expanded) % 64)
    compressed = pack_zero_masks(expanded)
    if len(compressed) > 0xFFFF:
        raise ValueError("encoded FRR compressed stream exceeds 65535 bytes")

    compressed_end = decoded.compressed_offset + decoded.compressed_size
    output = bytearray(source_gpc[: decoded.compressed_offset])
    output.extend(compressed)
    output.extend(source_gpc[compressed_end:])
    struct.pack_into("<H", output, decoded.descriptor_offset + 4, len(compressed))
    struct.pack_into("<I", output, 0x20, len(output))
    return bytes(output), b"".join(stream_rows)


def encode_standard_gpc(
    source_gpc: bytes,
    indices: bytes,
    *,
    output_mode: int,
) -> tuple[bytes, bytes]:
    """Encode a GPC while preserving its header, strides, and interlace."""
    decoded = decode_gpc(source_gpc, output_mode=output_mode)
    if len(indices) != decoded.width * decoded.height:
        raise ValueError("indexed image has an invalid size")
    if max(indices) >= 16:
        raise ValueError("indexed image contains a palette index above 15")

    logical_rows = indices_to_logical_rows(indices, decoded.width, decoded.height)
    stream_rows = [
        logical_rows[y]
        for first_y in range(decoded.interlace)
        for y in range(first_y, decoded.height, decoded.interlace)
    ]
    vertical_rows = inverse_vertical_xor(stream_rows)

    row_size = 1 + len(stream_rows[0])
    original_expanded, _ = unpack_zero_masks(
        source_gpc[
            decoded.compressed_offset : decoded.compressed_offset
            + decoded.compressed_size
        ],
        row_size * decoded.height,
    )
    original_strides = original_expanded[::row_size]
    expanded = bytearray().join(
        bytes((stride,)) + inverse_horizontal_xor(row, stride)
        for row, stride in zip(vertical_rows, original_strides)
    )
    expanded += bytes(-len(expanded) % 64)
    compressed = pack_zero_masks(expanded)
    if len(compressed) > 0xFFFF:
        raise ValueError("encoded GPC compressed stream exceeds 65535 bytes")

    compressed_end = decoded.compressed_offset + decoded.compressed_size
    output = bytearray(source_gpc[: decoded.compressed_offset])
    output.extend(compressed)
    output.extend(source_gpc[compressed_end:])
    struct.pack_into("<H", output, decoded.descriptor_offset + 4, len(compressed))
    struct.pack_into("<I", output, 0x20, len(output))
    return bytes(output), b"".join(stream_rows)


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
