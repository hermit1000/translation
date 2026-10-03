"""Shared ADV98 GPC encoding and decoding verified across five games."""

from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass


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


def decode_packed_palette_dac(data: bytes) -> tuple[tuple[int, int, int], ...]:
    """Express packed palette colors using six-bit DAC bit replication."""
    return tuple(
        tuple(((channel >> 2) << 2) | ((channel >> 2) >> 4) for channel in color)
        for color in decode_packed_palette(data)
    )


def undo_xor_delta(encoded_row: bytes) -> bytes:
    """Carry AL across stride chains as in the verified ADV98 routines."""
    if not encoded_row:
        raise ValueError("GPC row is empty")
    stride = encoded_row[0]
    row = bytearray(encoded_row[1:])
    if stride:
        accumulator = row[0]
        offset = stride
        for chain in range(stride):
            while offset < len(row):
                row[offset] ^= accumulator
                accumulator = row[offset]
                offset += stride
            # The runtime resets SI, but carries AL into the next chain.
            offset = chain + 1
    return bytes(row)


# Compatibility with the earlier game-specific entry point.
undo_xor_delta_runtime = undo_xor_delta


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


def _normalize_necronomicon_gpc(data: bytes) -> bytes:
    """Normalize Necronomicon's GPC header and legacy stream padding.

    Necronomicon leaves the declared file size as zero and stores the
    descriptor's compressed size including the 16-byte descriptor itself.
    The common decoder expects the normalized form, so only a temporary copy
    of the header is adjusted before decoding.
    """
    if len(data) < 0x30:
        raise ValueError("GPC file is shorter than its header")

    normalized = bytearray(data)
    if struct.unpack_from("<I", normalized, 0x20)[0] == 0:
        struct.pack_into("<I", normalized, 0x20, len(data))

    descriptor_offset = struct.unpack_from("<I", normalized, 0x18)[0]
    if descriptor_offset + 6 > len(normalized):
        raise ValueError("GPC descriptor is outside the file")
    compressed_size = struct.unpack_from("<H", normalized, descriptor_offset + 4)[0]
    compressed_end = descriptor_offset + 0x10 + compressed_size
    if compressed_end > len(normalized):
        inclusive_end = descriptor_offset + compressed_size
        if compressed_size >= 0x10 and inclusive_end == len(normalized):
            struct.pack_into(
                "<H", normalized, descriptor_offset + 4, compressed_size - 0x10
            )

    # A few legacy resources contain one or more nonzero bytes after the
    # complete zero-mask stream. They are padding, not image data.
    width, height = struct.unpack_from("<HH", normalized, descriptor_offset)
    planes = struct.unpack_from("<H", normalized, descriptor_offset + 8)[0]
    width_bytes = (width + 7) // 8
    compressed_offset = descriptor_offset + 0x10
    normalized_size = struct.unpack_from("<H", normalized, descriptor_offset + 4)[0]
    stream_end = compressed_offset + normalized_size
    target_size = (1 + width_bytes * planes) * height
    _, consumed = unpack_zero_masks(
        bytes(normalized[compressed_offset:stream_end]), target_size
    )
    for offset in range(compressed_offset + consumed, stream_end):
        normalized[offset] = 0

    return bytes(normalized)


def decode_gpc(
    data: bytes, *, output_mode: int = 0,
    palette_decoder: Callable[[bytes], tuple[tuple[int, int, int], ...]] = decode_packed_palette,
    variant: str = "standard",
    cumulative_xor: bool = True,
) -> GPCImage:
    if variant not in ("standard", "necronomicon"):
        raise ValueError(f"unsupported GPC variant {variant}")
    if variant == "necronomicon":
        data = _normalize_necronomicon_gpc(data)
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
    palette = palette_decoder(data[palette_offset + 4 : palette_offset + 36])

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
    if output_mode not in (0, 1):
        raise ValueError(f"unsupported GPC output mode {output_mode}")
    stream_rows = (
        apply_output_mode(encoded_rows, output_mode) if cumulative_xor else encoded_rows
    )
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
        planar=b"".join(logical_rows if variant == "necronomicon" else stream_rows),
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
    accumulator = row[0]
    offset = stride
    for chain in range(stride):
        while offset < len(row):
            encoded[offset] = row[offset] ^ accumulator
            accumulator = row[offset]
            offset += stride
        offset = chain + 1
    return bytes(encoded)


def encode_gpc(
    source_gpc: bytes,
    indices: bytes,
    *,
    output_mode: int = 0,
    variant: str = "standard",
    cumulative_xor: bool = True,
) -> tuple[bytes, bytes]:
    """Encode a GPC while preserving its header, strides, and interlace."""
    decoded = decode_gpc(
        source_gpc, output_mode=output_mode, variant=variant,
        cumulative_xor=cumulative_xor,
    )
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
    vertical_rows = inverse_vertical_xor(stream_rows) if cumulative_xor else stream_rows

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
    stored_size = len(compressed)
    if (
        variant == "necronomicon"
        and u16(source_gpc, decoded.descriptor_offset + 4)
        == decoded.compressed_size + DESCRIPTOR_SIZE
    ):
        stored_size += DESCRIPTOR_SIZE
    if stored_size > 0xFFFF:
        raise ValueError("encoded GPC descriptor size exceeds 65535 bytes")
    struct.pack_into("<H", output, decoded.descriptor_offset + 4, stored_size)
    if u32(source_gpc, 0x20):
        struct.pack_into("<I", output, 0x20, len(output))
    return bytes(output), b"".join(stream_rows)


# Compatibility with callers using the previous encoder name.
encode_standard_gpc = encode_gpc
