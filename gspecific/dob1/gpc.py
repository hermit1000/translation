"""Decoder for Dead of the Brain PC-98 ``.GPC`` images."""

from __future__ import annotations

import argparse
import json
import struct
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from module.pc98_image.indexed import IndexedImage
from module.pc98_image.pillow_adapter import to_pillow


SIGNATURE = b"PC98)GPCFILE   \0"
HEADER_SIZE = 0x30
DESCRIPTOR_SIZE = 0x10
PLANES = 4


def u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise EOFError(f"word at 0x{offset:X} is outside the GPC file")
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise EOFError(f"dword at 0x{offset:X} is outside the GPC file")
    return struct.unpack_from("<I", data, offset)[0]


@dataclass(frozen=True)
class GPCImage:
    source_size: int
    interlace: int
    width: int
    height: int
    x: int
    y: int
    palette: tuple[tuple[int, int, int], ...]
    planar: bytes
    indices: bytes
    palette_offset: int
    descriptor_offset: int
    compressed_offset: int
    compressed_size: int
    compressed_consumed: int
    compressed_padding_size: int
    descriptor_unknown_06: int
    descriptor_planes: int
    descriptor_flags: int
    output_mode: int


def decode_packed_palette(data: bytes) -> tuple[tuple[int, int, int], ...]:
    """Decode ADV98's 16 packed ``0x0GRB`` palette words."""
    if len(data) != 32:
        raise ValueError(f"GPC palette must be 32 bytes, got {len(data)}")
    colors = []
    for offset in range(0, len(data), 2):
        red_blue, green = data[offset : offset + 2]
        if green > 0x0F:
            raise ValueError(f"invalid packed palette word at entry {offset // 2}")
        colors.append(
            (
                (red_blue >> 4) * 17,
                green * 17,
                (red_blue & 0x0F) * 17,
            )
        )
    return tuple(colors)


def unpack_zero_masks(data: bytes, target_size: int) -> tuple[bytes, int]:
    """Expand the nested 8-bit zero masks used by GPC image data."""
    source = 0
    output = bytearray()
    while len(output) < target_size:
        if source >= len(data):
            raise EOFError(f"GPC stream ended at output byte {len(output)}")
        group_mask = data[source]
        source += 1
        for group_bit in range(8):
            if group_mask & (0x80 >> group_bit):
                if source >= len(data):
                    raise EOFError("GPC stream ended before a literal mask")
                literal_mask = data[source]
                source += 1
                for literal_bit in range(8):
                    if literal_mask & (0x80 >> literal_bit):
                        if source >= len(data):
                            raise EOFError("GPC stream ended before a literal byte")
                        output.append(data[source])
                        source += 1
                    else:
                        output.append(0)
            else:
                output.extend(b"\0" * 8)
    return bytes(output[:target_size]), source


def pack_zero_masks(data: bytes) -> bytes:
    """Pack bytes using ADV98's nested 8-bit zero masks."""
    if len(data) % 64:
        raise ValueError("GPC zero-mask input size must be a multiple of 64")

    output = bytearray()
    for group_start in range(0, len(data), 64):
        block = data[group_start : group_start + 64]
        group_mask = 0
        groups = []
        for group_index in range(8):
            group = block[group_index * 8 : (group_index + 1) * 8]
            literal_mask = 0
            literals = bytearray()
            for literal_index, value in enumerate(group):
                if value:
                    literal_mask |= 0x80 >> literal_index
                    literals.append(value)
            if literal_mask:
                group_mask |= 0x80 >> group_index
                groups.append(bytes((literal_mask,)) + literals)
            else:
                groups.append(b"")
        output.append(group_mask)
        for group in groups:
            output.extend(group)
    return bytes(output)


def undo_xor_delta(row: bytes) -> bytes:
    """Undo the per-row stride delta applied after zero-mask expansion."""
    if not row:
        raise ValueError("GPC row is empty")
    stride = row[0]
    output = bytearray(row[1:])
    if stride:
        for start in range(min(stride, len(output))):
            for offset in range(start + stride, len(output), stride):
                output[offset] ^= output[offset - stride]
    return bytes(output)


def planar_rows_to_indices(
    rows: list[bytes], width: int, height: int
) -> bytes:
    width_bytes = (width + 7) // 8
    padded_width = width_bytes * 8
    indices = bytearray(width * height)
    for y, row in enumerate(rows):
        if len(row) != width_bytes * PLANES:
            raise ValueError(f"row {y} has invalid planar size {len(row)}")
        for plane in range(PLANES):
            plane_row = row[plane * width_bytes : (plane + 1) * width_bytes]
            for x_byte, value in enumerate(plane_row):
                for bit in range(8):
                    x = x_byte * 8 + bit
                    if x < width and value & (0x80 >> bit):
                        indices[y * width + x] |= 1 << plane
        if padded_width < width:
            raise AssertionError("invalid padded width")
    return bytes(indices)


def apply_output_mode(rows: list[bytes], output_mode: int) -> list[bytes]:
    """Undo ADV98's cumulative row XOR before either mode writes VRAM."""
    if output_mode not in (0, 1):
        raise ValueError(f"unsupported GPC output mode {output_mode}")

    output = []
    previous = None
    for row in rows:
        if previous is not None:
            row = bytes(current ^ prior for current, prior in zip(row, previous))
        output.append(row)
        previous = row
    return output


def decode_gpc(data: bytes, *, output_mode: int = 0) -> GPCImage:
    if len(data) < HEADER_SIZE or data[:16] != SIGNATURE:
        raise ValueError("not an ADV98 PC-98 GPC file")

    interlace = u16(data, 0x10)
    palette_offset = u32(data, 0x14)
    descriptor_offset = u32(data, 0x18)
    declared_size = u32(data, 0x20)
    if declared_size != len(data):
        raise ValueError(
            f"GPC size mismatch: header={declared_size}, actual={len(data)}"
        )
    if not 1 <= interlace:
        raise ValueError(f"invalid GPC interlace count {interlace}")

    palette_count = u16(data, palette_offset)
    palette_format = u16(data, palette_offset + 2)
    if palette_count != 16 or palette_format != 2:
        raise ValueError(
            f"unsupported GPC palette {palette_count} colors, format {palette_format}"
        )
    palette = decode_packed_palette(data[palette_offset + 4 : palette_offset + 36])

    if descriptor_offset + DESCRIPTOR_SIZE > len(data):
        raise EOFError("GPC image descriptor extends beyond the file")
    width = u16(data, descriptor_offset)
    height = u16(data, descriptor_offset + 2)
    compressed_size = u16(data, descriptor_offset + 4)
    unknown_06 = u16(data, descriptor_offset + 6)
    planes = u16(data, descriptor_offset + 8)
    x = u16(data, descriptor_offset + 0x0A)
    y = u16(data, descriptor_offset + 0x0C)
    flags = u16(data, descriptor_offset + 0x0E)
    compressed_offset = descriptor_offset + DESCRIPTOR_SIZE
    compressed_end = compressed_offset + compressed_size
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid GPC dimensions {width}x{height}")
    if interlace > height:
        raise ValueError(
            f"GPC interlace count {interlace} exceeds image height {height}"
        )
    if planes != PLANES:
        raise ValueError(f"unsupported GPC plane count {planes}")
    if compressed_end > len(data):
        raise EOFError("GPC compressed image extends beyond the file")

    width_bytes = (width + 7) // 8
    encoded_row_size = 1 + width_bytes * PLANES
    expanded, consumed = unpack_zero_masks(
        data[compressed_offset:compressed_end], encoded_row_size * height
    )
    compressed_padding = data[compressed_offset + consumed : compressed_end]
    if any(compressed_padding):
        raise ValueError(
            f"GPC stream has {len(compressed_padding)} nonzero trailing bytes"
        )

    encoded_rows = [
        undo_xor_delta(expanded[offset : offset + encoded_row_size])
        for offset in range(0, len(expanded), encoded_row_size)
    ]
    stream_rows = apply_output_mode(encoded_rows, output_mode)
    rows: list[bytes | None] = [None] * height
    stream_index = 0
    for first_y in range(interlace):
        for row_y in range(first_y, height, interlace):
            rows[row_y] = stream_rows[stream_index]
            stream_index += 1
    if stream_index != height or any(row is None for row in rows):
        raise ValueError("GPC interlaced rows did not cover the image")
    logical_rows = [row for row in rows if row is not None]
    indices = planar_rows_to_indices(logical_rows, width, height)

    return GPCImage(
        source_size=len(data),
        interlace=interlace,
        width=width,
        height=height,
        x=x,
        y=y,
        palette=palette,
        planar=b"".join(stream_rows),
        indices=indices,
        palette_offset=palette_offset,
        descriptor_offset=descriptor_offset,
        compressed_offset=compressed_offset,
        compressed_size=compressed_size,
        compressed_consumed=consumed,
        compressed_padding_size=len(compressed_padding),
        descriptor_unknown_06=unknown_06,
        descriptor_planes=planes,
        descriptor_flags=flags,
        output_mode=output_mode,
    )


def write_artifacts(
    source: Path,
    output: Path,
    *,
    output_mode: int = 0,
    observed_modes: dict[int, int] | None = None,
) -> GPCImage:
    data = source.read_bytes()
    decoded = decode_gpc(data, output_mode=output_mode)
    output.mkdir(parents=True, exist_ok=True)
    stem = source.stem

    (output / f"{stem}.jpn{source.suffix}").write_bytes(data)
    (output / f"{stem}.pln.jpn.bin").write_bytes(decoded.planar)
    (output / f"{stem}.idx.jpn.bin").write_bytes(decoded.indices)
    image = IndexedImage.create(
        decoded.width, decoded.height, decoded.indices, decoded.palette
    )
    to_pillow(image).save(output / f"{stem}.jpn.png")

    metadata = {
        "source": str(source.relative_to(source.parents[1])).replace("\\", "/"),
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
            str(mode): count for mode, count in sorted((observed_modes or {}).items())
        },
    }
    metadata_text = json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    (output / f"{stem}.meta.json").write_text(
        metadata_text.replace("\n", "\r\n"),
        encoding="utf-8",
        newline="",
    )
    return decoded


def collect_gpc_output_modes(mes_root: Path) -> dict[str, Counter[int]]:
    """Collect C9/CF file and output-mode pairs from lexical MES decoding."""
    from gspecific.dob1.adv98_mes.decode_mes import decode_mes

    usage: defaultdict[str, Counter[int]] = defaultdict(Counter)
    for path in sorted(mes_root.glob("*.MES")):
        data = path.read_bytes()
        current_name = None
        for token in decode_mes(data):
            if token.get("type") != "command":
                continue
            opcode = token["bytes"][0]
            offset = token["offset"]
            if opcode == 0xC9 and offset + 1 < len(data) and data[offset + 1] == 0x22:
                end = data.find(b'"', offset + 2)
                if end >= 0:
                    value = data[offset + 2 : end].decode("ascii", errors="replace")
                    current_name = value.replace("\\", "/").rsplit("/", 1)[-1].upper()
            elif opcode == 0xCF and current_name and offset + 1 < len(data):
                encoded_mode = data[offset + 1]
                if 0x23 <= encoded_mode <= 0x27:
                    usage[current_name][encoded_mode - 0x23] += 1
    return dict(usage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        help="GRAPH-relative GPC name; may be repeated (default: all GPC files)",
    )
    parser.add_argument(
        "--mode",
        type=int,
        choices=(0, 1),
        help="force one GPC output mode instead of inferring it from MES usage",
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_root = workspace / "jpn-pc98" / "GRAPH"
    names = args.files or [path.name for path in sorted(source_root.glob("*.GPC"))]
    if not names:
        raise FileNotFoundError(f"no GPC files found under {source_root}")

    observed = collect_gpc_output_modes(workspace / "jpn-pc98" / "MES")

    for name in names:
        source = source_root / name
        if not source.is_file():
            raise FileNotFoundError(source)
        output = workspace / "image-pc98" / "GRAPH" / source.name
        modes = observed.get(source.name.upper(), Counter())
        output_mode = args.mode
        if output_mode is None:
            output_mode = modes.most_common(1)[0][0] if modes else 1
        decoded = write_artifacts(
            source,
            output,
            output_mode=output_mode,
            observed_modes=dict(modes),
        )
        print(
            f"{source.name}: {decoded.width}x{decoded.height}, "
            f"mode={decoded.output_mode}, compressed={decoded.compressed_size}, "
            f"output={output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
