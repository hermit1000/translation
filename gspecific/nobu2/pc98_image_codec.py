"""Nobunaga Zenkokuban PC-98 image codec helpers."""

from PIL import Image
from pathlib import Path

from module.pc98_image.indexed import IndexedImage
from module.pc98_image.palette import (
    PC98_PALETTE_3BPP,
    nearest_palette_index,
)
from module.pc98_image.pillow_adapter import to_pillow
from module.pc98_image.planar import (
    decode_interleaved_planar,
    encode_interleaved_planar,
)

PAK_MARKER = 0x96


def decode_planar(raw: bytes, width: int, height: int):
    """Decode interleaved B/R/G planar bytes into a paletted Pillow image."""
    pixels = decode_interleaved_planar(raw, width, height, 3)
    indexed = IndexedImage.create(width, height, pixels, PC98_PALETTE_3BPP)
    return to_pillow(indexed), pixels


def image_to_planar(
    image_source: str | Path | Image.Image,
    width: int,
    height: int,
) -> tuple[bytes, bytes]:
    """Quantize an image to PC-98 3bpp and encode interleaved B/R/G bytes."""
    image = (
        image_source.convert("RGB")
        if isinstance(image_source, Image.Image)
        else Image.open(image_source).convert("RGB")
    )
    if image.size != (width, height):
        raise ValueError(
            f"image size mismatch: got {image.width}x{image.height}, "
            f"expected {width}x{height}"
        )
    pixels = bytes(
        nearest_palette_index(rgb, PC98_PALETTE_3BPP)
        for rgb in image.getdata()
    )
    return encode_interleaved_planar(pixels, width, height, 3), pixels


def unpack_pak(
    data: bytes,
    width: int,
    height: int,
    literal_rows: int,
    copy_rows: int,
) -> tuple[bytes, int]:
    """Decode Nobu2's 0x96 vertical-copy stream."""
    if width <= 0 or width % 8:
        raise ValueError("PAK width must be positive and divisible by 8")
    if height <= 0 or literal_rows <= 0 or copy_rows <= 0:
        raise ValueError("PAK row counts must be positive")

    stride = width // 8 * 3
    literal_size = stride * literal_rows
    copy_distance = stride * copy_rows
    target_size = stride * height
    if literal_size > target_size:
        raise ValueError("literal rows exceed image height")
    if len(data) < literal_size:
        raise EOFError(
            f"PAK needs {literal_size} literal bytes, got {len(data)}"
        )

    output = bytearray(data[:literal_size])
    source = literal_size
    while len(output) < target_size:
        if source >= len(data):
            raise EOFError(f"PAK ended at output byte {len(output)}")
        value = data[source]
        source += 1
        if value != PAK_MARKER:
            output.append(value)
            continue

        if source >= len(data):
            raise EOFError("PAK ends after a 0x96 marker")
        count = data[source]
        source += 1
        if count == 1:
            output.append(PAK_MARKER)
            continue

        repeat = count or 256
        if len(output) < copy_distance:
            raise ValueError("PAK copy references unavailable output")
        for _ in range(repeat):
            if len(output) >= target_size:
                break
            output.append(output[-copy_distance])

    return bytes(output), source


def decode_pak(
    data: bytes,
    width: int,
    height: int,
    literal_rows: int,
    copy_rows: int,
):
    """Decode one complete PAK file and return image, planar bytes, and metadata."""
    planar, consumed = unpack_pak(
        data, width, height, literal_rows, copy_rows
    )
    image, pixels = decode_planar(planar, width, height)
    return image, planar, pixels, {
        "width": width,
        "height": height,
        "literal_rows": literal_rows,
        "vertical_copy_rows": copy_rows,
        "compressed_size": consumed,
        "padding_size": len(data) - consumed,
    }


def encode_pak(
    planar: bytes,
    width: int,
    height: int,
    literal_rows: int,
    copy_rows: int,
) -> bytes:
    """Encode planar bytes with Nobu2's 0x96 vertical-copy format."""
    if width <= 0 or width % 8:
        raise ValueError("PAK width must be positive and divisible by 8")
    if height <= 0 or literal_rows <= 0 or copy_rows <= 0:
        raise ValueError("PAK row counts must be positive")
    stride = width // 8 * 3
    expected = stride * height
    if len(planar) != expected:
        raise ValueError(
            f"planar size mismatch: got {len(planar)}, expected {expected}"
        )

    literal_size = stride * literal_rows
    copy_distance = stride * copy_rows
    if literal_size > expected or literal_size < copy_distance:
        raise ValueError("invalid PAK literal/copy row relationship")

    output = bytearray(planar[:literal_size])
    position = literal_size
    while position < len(planar):
        run = 0
        while (
            run < 256
            and position + run < len(planar)
            and planar[position + run]
            == planar[position + run - copy_distance]
        ):
            run += 1
        if run >= 2:
            output.extend((PAK_MARKER, 0 if run == 256 else run))
            position += run
            continue

        value = planar[position]
        output.extend((PAK_MARKER, 1) if value == PAK_MARKER else (value,))
        position += 1
    return bytes(output)
