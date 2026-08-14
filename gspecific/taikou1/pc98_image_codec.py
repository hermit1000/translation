#!/usr/bin/env python3
"""Shared PC-98 planar and RLE/LZ image decoding helpers."""

import json
import struct
from pathlib import Path

from PIL import Image

from module.pc98_image.indexed import IndexedImage
from module.pc98_image.palette import (
    PC98_PALETTE_3BPP as PALETTE_3BPP,
    PC98_PALETTE_4BPP as PALETTE_4BPP,
    nearest_palette_index,
)
from module.pc98_image.pillow_adapter import to_pillow
from module.pc98_image.planar import (
    decode_interleaved_planar,
    encode_interleaved_planar,
)

RLE_LZ_STRIDE_GROUPS = 0xA0


def indexed_image(width, height, pixel_indices, planes=3):
    palette_colors = PALETTE_3BPP if planes == 3 else PALETTE_4BPP
    return to_pillow(
        IndexedImage.create(width, height, pixel_indices, palette_colors)
    )


def image_to_planar(image_source, width, height, planes=3):
    """Convert an image to insertion-ready 3bpp B/R/G or 4bpp B/R/G/I planar bytes."""
    if planes not in (3, 4):
        raise ValueError("planes must be 3 or 4")
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
    palette = PALETTE_3BPP if planes == 3 else PALETTE_4BPP
    pixels = bytes(nearest_palette_index(rgb, palette) for rgb in image.getdata())
    return encode_planar_indices(pixels, width, height, planes), pixels


def image_to_rle_lz_groups(image_source):
    """Convert a PNG/PIL image to 3bpp B/R/G groups of four horizontal pixels."""
    image = (
        image_source.convert("RGB")
        if isinstance(image_source, Image.Image)
        else Image.open(image_source).convert("RGB")
    )
    width, height = image.size
    if width <= 0 or height <= 0 or width > 640 or height > 400:
        raise ValueError(f"unsupported RLE/LZ image size {width}x{height}")

    groups_per_line = (width + 3) >> 2
    pixels = image.load()
    rows = []
    for y in range(height):
        row = []
        for group in range(groups_per_line):
            blue_pattern = red_pattern = green_pattern = 0
            for pixel_index in range(4):
                x = group * 4 + pixel_index
                color = (
                    0
                    if x >= width
                    else nearest_palette_index(pixels[x, y], PALETTE_3BPP)
                )
                mask = 1 << (3 - pixel_index)
                if color & 1:
                    blue_pattern |= mask
                if color & 2:
                    red_pattern |= mask
                if color & 4:
                    green_pattern |= mask
            row.append((blue_pattern, red_pattern, green_pattern))
        rows.append(row)
    return width, height, rows


def _find_rle_lz_copy(flat, position, target, remaining):
    best_distance = None
    best_count = 0
    distances = [
        1,
        2,
        3,
        4,
        RLE_LZ_STRIDE_GROUPS,
        RLE_LZ_STRIDE_GROUPS * 2,
        RLE_LZ_STRIDE_GROUPS * 3,
        RLE_LZ_STRIDE_GROUPS * 4,
    ]
    for distance in distances:
        if position - distance < 0:
            continue
        count = 0
        while count < min(16, remaining):
            source_position = position + count - distance
            source = (
                flat.get(source_position)
                if source_position < position
                else target[count - distance]
            )
            if source is None or source != target[count]:
                break
            count += 1
        if count > best_count:
            best_distance = distance
            best_count = count
    return best_distance, best_count


def encode_rle_lz_groups(width, height, rows):
    """Encode four-pixel, 3bpp B/R/G groups with the PC-98 RLE/LZ format."""
    groups_per_line = (width + 3) >> 2
    if len(rows) != height or any(len(row) != groups_per_line for row in rows):
        raise ValueError("RLE/LZ group dimensions do not match width and height")

    output = bytearray(struct.pack("<HH", width, height))
    flat = {}
    for y, row in enumerate(rows):
        x = 0
        while x < groups_per_line:
            position = y * RLE_LZ_STRIDE_GROUPS + x
            remaining = groups_per_line - x
            distance, count = _find_rle_lz_copy(flat, position, row[x:], remaining)
            if count:
                if distance <= 4:
                    control = 0x80 | ((distance - 1) << 4) | (count - 1)
                else:
                    lines = distance // RLE_LZ_STRIDE_GROUPS
                    control = 0xC0 | ((lines - 1) << 4) | (count - 1)
                output.append(control)
                for index in range(count):
                    flat[position + index] = flat[position + index - distance]
                x += count
                continue

            current = row[x]
            run = 1
            while x + run < groups_per_line and run < 8 and row[x + run] == current:
                run += 1
            blue, red, green = current
            output.append(((run - 1) << 4) | green)
            output.append((red << 4) | blue)
            for index in range(run):
                flat[position + index] = current
            x += run
    return bytes(output)


def encode_rle_lz_image(image_source):
    """Quantize a PNG/PIL image to 3bpp B/R/G and return RLE/LZ-compressed bytes."""
    width, height, rows = image_to_rle_lz_groups(image_source)
    return encode_rle_lz_groups(width, height, rows)


def decode_planar(raw, width, height, planes=3):
    """Decode interleaved 3bpp B/R/G or 4bpp B/R/G/I, eight pixels per group."""
    if planes not in (3, 4):
        raise ValueError("planes must be 3 or 4")
    pixels = decode_interleaved_planar(raw, width, height, planes)
    return indexed_image(width, height, pixels, planes), bytes(pixels)


def encode_planar_indices(pixel_indices, width, height, planes=3):
    """Encode palette indices as interleaved 3bpp B/R/G or 4bpp B/R/G/I bytes."""
    if planes not in (3, 4):
        raise ValueError("planes must be 3 or 4")
    return encode_interleaved_planar(pixel_indices, width, height, planes)


def decode_rle_lz(raw, offset=0):
    """Decode a 3bpp B/R/G OPEN/GRAPH RLE/LZ block with a <width,height> header."""
    start = offset
    if offset + 4 > len(raw):
        raise EOFError("RLE/LZ header outside input")
    width, height = struct.unpack_from("<HH", raw, offset)
    if not (1 <= width <= 640 and 1 <= height <= 400):
        raise ValueError(f"invalid RLE/LZ dimensions {width}x{height}")
    offset += 4

    groups_per_line = (width + 3) >> 2
    groups = {}
    for y in range(height):
        x = 0
        while x < groups_per_line:
            if offset >= len(raw):
                raise EOFError("RLE/LZ control byte outside input")
            control = raw[offset]
            offset += 1
            if control & 0x80:
                count = (control & 0x0F) + 1
                distance = (
                    (((control >> 4) & 3) + 1) * RLE_LZ_STRIDE_GROUPS
                    if control & 0x40
                    else ((control >> 4) & 3) + 1
                )
                if x + count > groups_per_line:
                    raise ValueError("RLE/LZ copy crosses scanline")
                for _ in range(count):
                    position = y * RLE_LZ_STRIDE_GROUPS + x
                    source = position - distance
                    if source not in groups:
                        raise ValueError("RLE/LZ copy references unavailable data")
                    groups[position] = groups[source]
                    x += 1
            else:
                if offset >= len(raw):
                    raise EOFError("RLE/LZ literal outside input")
                count = ((control >> 4) & 7) + 1
                if x + count > groups_per_line:
                    raise ValueError("RLE/LZ literal crosses scanline")
                packed = raw[offset]
                offset += 1
                value = (packed & 0x0F, packed >> 4, control & 0x0F)
                for _ in range(count):
                    groups[y * RLE_LZ_STRIDE_GROUPS + x] = value
                    x += 1

    pixels = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            blue, red, green = groups[y * RLE_LZ_STRIDE_GROUPS + (x >> 2)]
            mask = 1 << (3 - (x & 3))
            pixels[y * width + x] = (
                (1 if blue & mask else 0)
                | (2 if red & mask else 0)
                | (4 if green & mask else 0)
            )

    image = indexed_image(width, height, pixels, 3)
    padded_width = (width + 7) & ~7
    padded_pixels = bytearray(padded_width * height)
    for y in range(height):
        padded_pixels[y * padded_width : y * padded_width + width] = pixels[y * width : (y + 1) * width]
    planar = encode_planar_indices(padded_pixels, padded_width, height, 3)
    return image, planar, bytes(pixels), {
        "offset": start,
        "next_offset": offset,
        "compressed_size": offset - start,
        "width": width,
        "height": height,
        "planar_width": padded_width,
    }


def parse_range(text):
    try:
        start_text, end_text = text.split("=", 1)
        start = int(start_text, 16)
        end = int(end_text, 16)
    except (ValueError, AttributeError) as error:
        raise ValueError(f"invalid manifest range {text!r}") from error
    if end < start:
        raise ValueError(f"range ends before it starts: {text}")
    return start, end


def load_manifest(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("manifest root must be an object")
    entries = []
    for range_text, value in data.items():
        start, end = parse_range(range_text)
        if isinstance(value, str):
            config = {"raw": value}
        elif isinstance(value, dict):
            config = dict(value)
            config.setdefault("raw", config.get("file"))
        else:
            raise ValueError(f"unsupported manifest value for {range_text}")
        if not config.get("raw"):
            raise ValueError(f"manifest entry {range_text} has no raw filename")
        entries.append({"range": range_text, "start": start, "end": end, **config})
    return entries
