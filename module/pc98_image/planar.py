"""Conversions between palette indices and explicit PC-98 planar layouts."""

from collections.abc import Callable


def _validate_dimensions(width: int, height: int, planes: int) -> None:
    if planes <= 0 or planes > 8:
        raise ValueError("planes must be between 1 and 8")
    if width <= 0 or height <= 0 or width % 8:
        raise ValueError("width must be positive and divisible by 8")


def _validate(indices: bytes | bytearray, width: int, height: int, planes: int) -> None:
    _validate_dimensions(width, height, planes)
    if len(indices) != width * height:
        raise ValueError("pixel index size does not match dimensions")
    limit = 1 << planes
    if any(index >= limit for index in indices):
        raise ValueError(f"pixel index does not fit in {planes} planes")


def _encode(
    indices: bytes | bytearray,
    width: int,
    height: int,
    planes: int,
    offset_for: Callable[[int, int, int], int],
) -> bytes:
    _validate(indices, width, height, planes)
    output = bytearray(width * height * planes // 8)
    for y in range(height):
        for x_byte in range(width // 8):
            base = y * width + x_byte * 8
            for plane in range(planes):
                value = 0
                for bit in range(8):
                    if indices[base + bit] & (1 << plane):
                        value |= 0x80 >> bit
                output[offset_for(plane, y, x_byte)] = value
    return bytes(output)


def _decode(
    raw: bytes | bytearray,
    width: int,
    height: int,
    planes: int,
    offset_for: Callable[[int, int, int], int],
) -> bytes:
    _validate_dimensions(width, height, planes)
    expected = width * height * planes // 8
    if len(raw) != expected:
        raise ValueError(f"planar size mismatch: got {len(raw)}, expected {expected}")
    indices = bytearray(width * height)
    for y in range(height):
        for x_byte in range(width // 8):
            base = y * width + x_byte * 8
            for plane in range(planes):
                value = raw[offset_for(plane, y, x_byte)]
                for bit in range(8):
                    if value & (0x80 >> bit):
                        indices[base + bit] |= 1 << plane
    return bytes(indices)


def encode_interleaved_planar(
    indices: bytes | bytearray, width: int, height: int, planes: int
) -> bytes:
    width_bytes = width // 8
    return _encode(
        indices,
        width,
        height,
        planes,
        lambda plane, y, x: (y * width_bytes + x) * planes + plane,
    )


def decode_interleaved_planar(
    raw: bytes | bytearray, width: int, height: int, planes: int
) -> bytes:
    width_bytes = width // 8
    return _decode(
        raw,
        width,
        height,
        planes,
        lambda plane, y, x: (y * width_bytes + x) * planes + plane,
    )


def encode_plane_major_row_planar(
    indices: bytes | bytearray, width: int, height: int, planes: int
) -> bytes:
    width_bytes = width // 8
    plane_size = width_bytes * height
    return _encode(
        indices,
        width,
        height,
        planes,
        lambda plane, y, x: plane * plane_size + y * width_bytes + x,
    )


def decode_plane_major_row_planar(
    raw: bytes | bytearray, width: int, height: int, planes: int
) -> bytes:
    width_bytes = width // 8
    plane_size = width_bytes * height
    return _decode(
        raw,
        width,
        height,
        planes,
        lambda plane, y, x: plane * plane_size + y * width_bytes + x,
    )


def encode_plane_major_column_planar(
    indices: bytes | bytearray, width: int, height: int, planes: int
) -> bytes:
    width_bytes = width // 8
    plane_size = width_bytes * height
    return _encode(
        indices,
        width,
        height,
        planes,
        lambda plane, y, x: plane * plane_size + x * height + y,
    )


def decode_plane_major_column_planar(
    raw: bytes | bytearray, width: int, height: int, planes: int
) -> bytes:
    width_bytes = width // 8
    plane_size = width_bytes * height
    return _decode(
        raw,
        width,
        height,
        planes,
        lambda plane, y, x: plane * plane_size + x * height + y,
    )


def encode_packed_4bpp(indices: bytes | bytearray, width: int, height: int) -> bytes:
    if width <= 0 or height <= 0 or len(indices) != width * height:
        raise ValueError("pixel index size does not match dimensions")
    if any(index > 0x0F for index in indices):
        raise ValueError("pixel index does not fit in 4bpp")
    output = bytearray()
    for y in range(height):
        row = indices[y * width : (y + 1) * width]
        for x in range(0, width, 2):
            right = row[x + 1] if x + 1 < width else 0
            output.append((row[x] << 4) | right)
    return bytes(output)


def decode_packed_4bpp(raw: bytes | bytearray, width: int, height: int) -> bytes:
    stride = (width + 1) // 2
    if width <= 0 or height <= 0 or len(raw) != stride * height:
        raise ValueError("packed 4bpp size does not match dimensions")
    indices = bytearray()
    for y in range(height):
        for value in raw[y * stride : (y + 1) * stride]:
            indices.extend((value >> 4, value & 0x0F))
    if width % 2:
        indices = bytearray(
            value
            for y in range(height)
            for value in indices[y * (width + 1) : y * (width + 1) + width]
        )
    return bytes(indices)
