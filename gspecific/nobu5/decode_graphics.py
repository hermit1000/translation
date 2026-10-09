#!/usr/bin/env python3
"""Extract verified PC-98 image resources from a workspace."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


PORTRAIT_FILES = {
    "KAO.NB5": 929,
    "KAO2.NB5": 128,
    "KAO3.NB5": 10,
}
ITEM_RECORD_SIZE = 0x438
ITEM_IMAGE_COUNT = 26
ITEM_WIDTH = 64
ITEM_HEIGHT = 45
GRAPH_KEYPAD_OFFSET = 0x585E
GRAPH_KEYPAD_SIZE = 0x0F3C
GRAPH_KEYPAD_WIDTH = 104
GRAPH_KEYPAD_HEIGHT = 100
SOPEN_IMAGE_COUNT = 55
NKAO_IMAGE_COUNT = 3
SLOGO_OFFSETS = (0x0000, 0x04E5, 0x07D6, 0x0C6D, 0x1232)
PACK_SECTORS = (
    0x000,
    0x039,
    0x077,
    0x0B1,
    0x0F3,
    0x0F6,
    0x0FB,
    0x101,
    0x10C,
    0x117,
    0x128,
    0x134,
    0x144,
    0x151,
    0x16C,
    0x17E,
    0x18A,
    0x194,
    0x19F,
    0x1A8,
    0x1AF,
    0x1B6,
    0x1BF,
    0x1D1,
    0x1E0,
    0x1EC,
    0x1F7,
)
PORTRAIT_SIGNATURE = b"\x40\x00\x50\x00"
PC98_PALETTE_8 = [
    (0x00, 0x00, 0x00),
    (0x00, 0x00, 0xFF),
    (0xFF, 0x00, 0x00),
    (0xFF, 0x00, 0xFF),
    (0x00, 0xFF, 0x00),
    (0x00, 0xFF, 0xFF),
    (0xFF, 0xFF, 0x00),
    (0xFF, 0xFF, 0xFF),
]
MAIN_PALETTE_00_BGR = [
    (0x0, 0x0, 0x0),
    (0x7, 0x2, 0x4),
    (0x0, 0xC, 0x4),
    (0x8, 0xE, 0xC),
    (0x2, 0x6, 0x8),
    (0xE, 0xB, 0xD),
    (0x2, 0xC, 0x9),
    (0xF, 0xF, 0xF),
]
SOPEN_PALETTE_BGR = [
    (0x0, 0x0, 0x0),
    (0x4, 0xB, 0x7),
    (0x3, 0x2, 0x4),
    (0x1, 0x0, 0x2),
    (0x2, 0x6, 0x5),
    (0x4, 0x0, 0x0),
    (0x6, 0xC, 0x9),
    (0xA, 0xC, 0xB),
    (0x0, 0x0, 0x0),
    (0xA, 0x0, 0x6),
    (0x2, 0xF, 0x4),
    (0xC, 0xF, 0xA),
    (0x4, 0x6, 0xA),
    (0xF, 0x8, 0xD),
    (0x6, 0xF, 0xC),
    (0xF, 0xF, 0xF),
]


def expand_pc98_component(value: int) -> int:
    value_6bit = value << 2 | value >> 2
    return value_6bit << 2 | value_6bit >> 4


SOPEN_PALETTE_16 = [
    tuple(expand_pc98_component(value) for value in (red, green, blue)) for blue, red, green in SOPEN_PALETTE_BGR
]
SOPEN_PALETTE_8 = SOPEN_PALETTE_16[:8]
MAIN_PALETTE_00_8 = [
    tuple(expand_pc98_component(value) for value in (red, green, blue)) for blue, red, green in MAIN_PALETTE_00_BGR
]

# Matched against workspace5 capture/main_002.raw1.png. Index 4 is unused
# in the verified keypad image; its actual color is unknown.
GRAPH_KEYPAD_PALETTE_8 = [
    (0x00, 0x00, 0x00),
    (0x30, 0x65, 0xAA),
    (0xCF, 0x45, 0x00),
    (0xEF, 0xCF, 0x9A),
    (0x00, 0x00, 0x00),
    (0xBA, 0xDF, 0xEF),
    (0xCF, 0xAA, 0x55),
    (0xEF, 0xEF, 0xFF),
]


class DecodeError(ValueError):
    pass


class NibbleReader:
    """Byte-RLE and high/low nibble reader from MAIN.EXE sub_1373A/sub_137A6."""

    def __init__(self, data: bytes, position: int):
        self.data = data
        self.position = position
        self.last = 0
        self.repeat = 0
        self.pending_low_nibble: int | None = None

    def read_byte(self) -> int:
        if self.repeat:
            self.repeat -= 1
            return self.last
        if self.position >= len(self.data):
            raise DecodeError("compressed byte stream ended early")
        value = self.data[self.position]
        self.position += 1
        if value != 0xFE:
            self.last = value
            return value
        if self.position >= len(self.data):
            raise DecodeError("truncated 0xFE escape")
        count = self.data[self.position]
        self.position += 1
        if count == 1:
            self.last = 0xFE
            return self.last
        self.repeat = 0x100 if count == 0 else count
        self.repeat -= 1
        return self.last

    def read_nibble(self) -> int:
        if self.pending_low_nibble is None:
            value = self.read_byte()
            self.pending_low_nibble = value & 0x0F
            return value >> 4
        value = self.pending_low_nibble
        self.pending_low_nibble = None
        return value


def decode_portrait(data: bytes, start: int) -> tuple[int, int, bytes, int]:
    """Decode MAIN.EXE sub_138F2 to row-major 3bpp indices."""
    if start + 4 > len(data):
        raise DecodeError("truncated portrait header")
    width = int.from_bytes(data[start : start + 2], "little")
    height = int.from_bytes(data[start + 2 : start + 4], "little")
    if width != 64 or height != 80:
        raise DecodeError(f"unexpected portrait dimensions {width}x{height}")

    reader = NibbleReader(data, start + 4)
    indices = bytearray(width * height)
    for y in range(height):
        reference = reader.read_nibble()
        run = 0
        for x in range(width):
            if not run:
                token = reader.read_nibble()
                if token & 0x08:
                    if token & 0x04:
                        run = (token & 3) * 16 + reader.read_nibble() + 6
                    else:
                        run = (token & 3) + 2
                else:
                    indices[y * width + x] = token & 7
                    continue

            if reference & 0x08:
                source_x = x
                source_y = y - reference + 7
            else:
                source_x = x - reference - 1
                source_y = y
            if source_x < 0 or source_y < 0:
                raise DecodeError(f"invalid reference at ({x}, {y}): nibble {reference}")
            indices[y * width + x] = indices[source_y * width + source_x]
            run -= 1
        if run:
            raise DecodeError(f"copy command crosses row {y}")
    return width, height, bytes(indices), reader.position


def encode_interleaved_planar(indices: bytes, width: int, height: int, planes: int) -> bytes:
    stride = width // 8
    output = bytearray(stride * height * planes)
    for y in range(height):
        for x_byte in range(stride):
            pixel = y * width + x_byte * 8
            target = (y * stride + x_byte) * planes
            for plane in range(planes):
                value = 0
                for bit in range(8):
                    if indices[pixel + bit] & (1 << plane):
                        value |= 0x80 >> bit
                output[target + plane] = value
    return bytes(output)


def decode_interleaved_planar(planar: bytes, width: int, height: int, planes: int) -> bytes:
    stride = width // 8
    expected_size = stride * height * planes
    if len(planar) != expected_size:
        raise DecodeError(f"interleaved planar size is {len(planar)}, expected {expected_size}")
    indices = bytearray(width * height)
    for y in range(height):
        for x_byte in range(stride):
            source = (y * stride + x_byte) * planes
            pixel = y * width + x_byte * 8
            for plane in range(planes):
                value = planar[source + plane]
                for bit in range(8):
                    if value & (0x80 >> bit):
                        indices[pixel + bit] |= 1 << plane
    return bytes(indices)


def save_png(
    output: Path,
    indices: bytes,
    width: int,
    height: int,
    palette: list[tuple[int, int, int]],
) -> None:
    rgb = bytes(component for index in indices for component in palette[index])
    Image.frombytes("RGB", (width, height), rgb).save(output)


def decode_sopen_image(data: bytes, start: int) -> tuple[int, int, bytes, bytes, bytes, int]:
    """Decode SOPEN.EXE sub_10CEF to four color planes and opaque pixels."""
    if start + 20 > len(data):
        raise DecodeError("truncated SOPEN image header")
    width = int.from_bytes(data[start : start + 2], "little") & 0x7FFF
    height = int.from_bytes(data[start + 2 : start + 4], "little")
    if not 1 <= width <= 640 or not 1 <= height <= 400:
        raise DecodeError(f"invalid SOPEN image dimensions {width}x{height}")

    groups_per_row = (width + 3) // 4
    patterns = [int.from_bytes(data[position : position + 2], "little") for position in range(start + 4, start + 20, 2)]
    groups: list[int] = []
    position = start + 20

    def read_byte() -> int:
        nonlocal position
        if position >= len(data):
            raise DecodeError("SOPEN compressed stream ended early")
        value = data[position]
        position += 1
        return value

    for row in range(height):
        row_end = len(groups) + groups_per_row
        while len(groups) < row_end:
            control = read_byte()
            if control & 0x80:
                count = (control & 0x0F) + 1
                distance = (((control >> 4) & 3) + 1) * groups_per_row if control & 0x40 else ((control >> 4) & 3) + 1
                if len(groups) + count > row_end:
                    raise DecodeError(f"SOPEN copy command crosses row {row}")
                if distance > len(groups):
                    raise DecodeError(f"SOPEN copy references unavailable data in row {row}")
                for _ in range(count):
                    groups.append(groups[-distance])
                continue

            count = (control & 7) + 1
            if len(groups) + count > row_end:
                raise DecodeError(f"SOPEN literal command crosses row {row}")
            selector = control & 0x78
            if selector == 0:
                pattern = 0
            elif control & 0x40:
                pattern = patterns[(control >> 3) & 7]
            elif selector == 0x38:
                high = read_byte()
                pattern = high << 8 | read_byte()
            else:
                value = read_byte()
                shorthand = selector >> 3
                if shorthand == 1:
                    pattern = value
                elif shorthand == 2:
                    pattern = (value & 0x0F) | (value & 0xF0) << 4
                elif shorthand == 3:
                    pattern = (value & 0x0F) | (value & 0xF0) << 8
                elif shorthand == 4:
                    pattern = value << 4
                elif shorthand == 5:
                    pattern = (value & 0x0F) << 4 | (value & 0xF0) << 8
                elif shorthand == 6:
                    pattern = value << 8
                else:
                    raise DecodeError(f"invalid SOPEN literal selector 0x{selector:02X}")
            groups.extend([pattern] * count)

    padded_width = (width + 7) & ~7
    planar = bytearray(padded_width // 8 * height * 4)
    indices = bytearray(width * height)
    alpha = bytearray([255]) * (width * height)
    for y in range(height):
        for group_x in range(groups_per_row):
            pattern = groups[y * groups_per_row + group_x]
            for plane in range(4):
                mask = (pattern >> (plane * 4)) & 0x0F
                planar_offset = (y * (padded_width // 8) + group_x // 2) * 4 + plane
                planar[planar_offset] |= mask << (4 if group_x % 2 == 0 else 0)
                for bit in range(4):
                    x = group_x * 4 + bit
                    if x < width and mask & (8 >> bit):
                        indices[y * width + x] |= 1 << plane
    return width, height, bytes(planar), bytes(indices), bytes(alpha), position


def decode_nkao_image(data: bytes, start: int) -> tuple[int, int, bytes, bytes, int]:
    """Decode NKAO.NB5 as 4bpp SOPEN-style image data."""
    width, height, planar, indices, _, position = decode_sopen_image(data, start)
    return width, height, planar, indices, position


def rotate_left(value: int, count: int, bits: int) -> int:
    mask = (1 << bits) - 1
    count %= bits
    return ((value << count) | (value >> (bits - count))) & mask


def decode_slogo_image(data: bytes, start: int, end: int) -> tuple[int, int, bytes, bytes, int]:
    """Decode the GRPDRVEX.EXE AH=19h format used by SLOGO.NB5."""
    if start + 4 > end:
        raise DecodeError("truncated SLOGO image header")
    width = int.from_bytes(data[start : start + 2], "little")
    height = int.from_bytes(data[start + 2 : start + 4], "little")
    if width % 8 or not 1 <= width <= 640 or not 1 <= height <= 400:
        raise DecodeError(f"invalid SLOGO image dimensions {width}x{height}")

    groups_per_row = (width + 3) // 4
    ring = bytearray(0x640)
    position = start + 4
    packed = bytearray()

    def read_byte() -> int:
        nonlocal position
        if position >= end:
            raise DecodeError("SLOGO compressed stream ended early")
        value = data[position]
        position += 1
        return value

    for row in range(height):
        slot = row % 5
        slot_start = slot * 0x140
        write_pos = slot_start
        row_bytes = bytearray()
        produced = 0
        while produced < groups_per_row:
            command = read_byte()
            if not command & 0x80:
                count = (command >> 4) + 1
                values = (read_byte(), command)
                for _ in range(count):
                    for value in values:
                        ring[write_pos] = value
                        write_pos += 1
                        row_bytes.append(value)
            else:
                count = (command & 0x0F) + 1
                selector = ((command >> 4) & 3) + 1
                if command & 0x40:
                    source_slot = (slot - selector) % 5
                    read_pos = source_slot * 0x140 + write_pos - slot_start
                else:
                    read_pos = write_pos - selector * 2
                for _ in range(count * 2):
                    value = ring[read_pos]
                    read_pos += 1
                    ring[write_pos % len(ring)] = value
                    write_pos += 1
                    row_bytes.append(value)

            produced += count
        packed.extend(row_bytes[: groups_per_row * 2])

    planar = bytearray(width // 8 * height * 3)
    for source in range(0, len(packed), 4):
        first = int.from_bytes(packed[source : source + 2], "little")
        second = int.from_bytes(packed[source + 2 : source + 4], "little")
        second_low = second & 0xFF
        first_high = first >> 8
        first = (first & 0x00FF) | second_low << 8
        second = (second & 0xFF00) | first_high
        first = rotate_left(first, 4, 16)
        first = (first & 0xFF00) | rotate_left(first & 0xFF, 4, 8)
        first = rotate_left(first, 12, 16)
        second = rotate_left(second, 4, 16)
        second = (second & 0xFF00) | rotate_left(second & 0xFF, 4, 8)
        second = rotate_left(second, 4, 16)
        target = source // 4 * 3
        planar[target : target + 3] = bytes((first >> 8, first & 0xFF, second & 0xFF))

    indices = bytearray(width * height)
    stride = width // 8
    for y in range(height):
        for x_byte in range(stride):
            plane_offset = (y * stride + x_byte) * 3
            for plane in range(3):
                value = planar[plane_offset + plane]
                for bit in range(8):
                    if value & (0x80 >> bit):
                        indices[y * width + x_byte * 8 + bit] |= 1 << plane
    return width, height, bytes(planar), bytes(indices), position


def extract_slogo(source: Path, input_root: Path, output_root: Path) -> int:
    data = source.read_bytes()
    relative = source.relative_to(input_root)
    directory = output_root / relative
    directory.mkdir(parents=True, exist_ok=True)
    ends = SLOGO_OFFSETS[1:] + (len(data),)

    for record_index, (start, end) in enumerate(zip(SLOGO_OFFSETS, ends)):
        width, height, planar, indices, stream_end = decode_slogo_image(data, start, end)
        if any(data[stream_end:end]):
            raise DecodeError(f"SLOGO record {record_index} has nonzero trailing data")
        stem = f"{start:06x}"
        block = data[start:end]
        (directory / f"{stem}.cmp.jpn.bin").write_bytes(block)
        (directory / f"{stem}.pln.jpn.bin").write_bytes(planar)
        (directory / f"{stem}.idx.jpn.bin").write_bytes(indices)
        save_png(directory / f"{stem}.jpn.png", indices, width, height, SOPEN_PALETTE_8)
        metadata = {
            "source": relative.as_posix(),
            "offset": f"0x{start:06X}",
            "original_size": len(block),
            "encoded_size": None,
            "stored_size": None,
            "padding_byte": None,
            "compression": "grpdrv-lz",
            "width": width,
            "height": height,
            "planes": 3,
            "plane_order": "BRG",
            "planar_layout": "interleaved",
            "bit_order": "msb-first",
            "stride": width // 8,
            "palette": [f"#{red:02X}{green:02X}{blue:02X}" for red, green, blue in SOPEN_PALETTE_8],
            "palette_source": "SOPEN.EXE file offset 0xBA14, first 8 B/R/G entries",
            "record_index": record_index,
            "header_size": 4,
            "compressed_stream_size": stream_end - start,
        }
        (directory / f"{stem}.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )
    print(f"{relative}: {len(SLOGO_OFFSETS)} compressed logo images")
    return len(SLOGO_OFFSETS)


def extract_sopen_archive(source: Path, input_root: Path, output_root: Path) -> int:
    data = source.read_bytes()
    relative = source.relative_to(input_root)
    directory = output_root / relative
    directory.mkdir(parents=True, exist_ok=True)

    spans = []
    start = 0
    while start < len(data):
        _, _, _, _, _, end = decode_sopen_image(data, start)
        spans.append((start, end))
        start = end
    if len(spans) != SOPEN_IMAGE_COUNT:
        raise DecodeError(f"SOPEN.NB5 contains {len(spans)} images, expected {SOPEN_IMAGE_COUNT}")

    for record_index, (start, end) in enumerate(spans):
        width, height, planar, indices, alpha, stream_end = decode_sopen_image(data, start)
        if stream_end > end:
            raise DecodeError(f"SOPEN record {record_index} overlaps the next record")
        if any(data[stream_end:end]):
            raise DecodeError(f"SOPEN record {record_index} has nonzero trailing data")

        stem = f"{start:06x}"
        block = data[start:end]
        (directory / f"{stem}.cmp.jpn.bin").write_bytes(block)
        (directory / f"{stem}.pln.jpn.bin").write_bytes(planar)
        (directory / f"{stem}.idx.jpn.bin").write_bytes(indices)
        # Keep the native indices, including distinct entries with the same RGB.
        image = Image.frombytes("P", (width, height), indices)
        image.putpalette([component for color in SOPEN_PALETTE_16 for component in color])
        image.save(directory / f"{stem}.jpn.png")
        metadata = {
            "source": relative.as_posix(),
            "offset": f"0x{start:06X}",
            "original_size": len(block),
            "encoded_size": None,
            "stored_size": None,
            "padding_byte": None,
            "compression": "sopen-rle-lz",
            "width": width,
            "height": height,
            "planes": 4,
            "color_planes": 4,
            "plane_order": "BRGI",
            "planar_layout": "interleaved",
            "bit_order": "msb-first",
            "stride": (width + 7) // 8,
            "alpha": "opaque; fourth plane is color bit 3",
            "palette": [f"#{red:02X}{green:02X}{blue:02X}" for red, green, blue in SOPEN_PALETTE_16],
            "palette_source": "SOPEN.EXE file offset 0xBA14, first 16 B/R/G entries",
            "record_index": record_index,
            "header_size": 20,
            "compressed_stream_size": stream_end - start,
        }
        (directory / f"{stem}.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )

    print(f"{relative}: {len(spans)} compressed images")
    return len(spans)


def extract_nkao_archive(source: Path, input_root: Path, output_root: Path) -> int:
    data = source.read_bytes()
    relative = source.relative_to(input_root)
    directory = output_root / relative
    directory.mkdir(parents=True, exist_ok=True)

    spans = []
    start = 0
    while start < len(data):
        _, _, _, _, _, end = decode_sopen_image(data, start)
        spans.append((start, end))
        start = end
    if len(spans) != NKAO_IMAGE_COUNT:
        raise DecodeError(f"NKAO.NB5 contains {len(spans)} images, expected {NKAO_IMAGE_COUNT}")

    for record_index, (start, end) in enumerate(spans):
        width, height, planar, indices, stream_end = decode_nkao_image(data, start)
        if stream_end != end:
            raise DecodeError(f"NKAO record {record_index} has trailing data")

        stem = f"{start:06x}"
        block = data[start:end]
        (directory / f"{stem}.cmp.jpn.bin").write_bytes(block)
        (directory / f"{stem}.pln.jpn.bin").write_bytes(planar)
        (directory / f"{stem}.idx.jpn.bin").write_bytes(indices)
        rgba = bytes(component for index in indices for component in (*SOPEN_PALETTE_16[index], 255))
        Image.frombytes("RGBA", (width, height), rgba).save(directory / f"{stem}.jpn.png")
        metadata = {
            "source": relative.as_posix(),
            "offset": f"0x{start:06X}",
            "original_size": len(block),
            "encoded_size": None,
            "stored_size": None,
            "padding_byte": None,
            "compression": "sopen-rle-lz",
            "width": width,
            "height": height,
            "planes": 4,
            "color_planes": 4,
            "plane_order": "BRGI",
            "planar_layout": "interleaved",
            "bit_order": "msb-first",
            "stride": (width + 7) // 8,
            "palette": [f"#{red:02X}{green:02X}{blue:02X}" for red, green, blue in SOPEN_PALETTE_16],
            "palette_source": "SOPEN.EXE file offset 0xBA14, first 16 B/R/G entries",
            "record_index": record_index,
            "header_size": 20,
            "compressed_stream_size": stream_end - start,
            "asm_reference": "SOPEN.EXE sub_15A5A loads NKAO.NB5 records and draws them via sub_10CEF",
        }
        (directory / f"{stem}.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )

    print(f"{relative}: {len(spans)} compressed SOPEN portrait images")
    return len(spans)


def extract_item_archive(source: Path, input_root: Path, output_root: Path) -> int:
    data = source.read_bytes()
    if len(data) % ITEM_RECORD_SIZE:
        raise DecodeError("ITEM.NB5 size is not divisible by 0x438")
    count = len(data) // ITEM_RECORD_SIZE
    if count != ITEM_IMAGE_COUNT:
        raise DecodeError(f"ITEM.NB5 contains {count} images, expected {ITEM_IMAGE_COUNT}")

    relative = source.relative_to(input_root)
    directory = output_root / relative
    directory.mkdir(parents=True, exist_ok=True)

    for record_index in range(count):
        offset = record_index * ITEM_RECORD_SIZE
        planar = data[offset : offset + ITEM_RECORD_SIZE]
        indices = decode_interleaved_planar(planar, ITEM_WIDTH, ITEM_HEIGHT, 3)
        stem = f"{offset:06x}"
        (directory / f"{stem}.pln.jpn.bin").write_bytes(planar)
        (directory / f"{stem}.idx.jpn.bin").write_bytes(indices)
        save_png(
            directory / f"{stem}.jpn.png",
            indices,
            ITEM_WIDTH,
            ITEM_HEIGHT,
            MAIN_PALETTE_00_8,
        )
        metadata = {
            "source": relative.as_posix(),
            "offset": f"0x{offset:06X}",
            "original_size": ITEM_RECORD_SIZE,
            "encoded_size": None,
            "stored_size": None,
            "padding_byte": None,
            "compression": "none",
            "width": ITEM_WIDTH,
            "height": ITEM_HEIGHT,
            "planes": 3,
            "plane_order": "BRG",
            "planar_layout": "interleaved",
            "bit_order": "msb-first",
            "stride": ITEM_WIDTH // 8,
            "palette": [f"#{red:02X}{green:02X}{blue:02X}" for red, green, blue in MAIN_PALETTE_00_8],
            "palette_source": "MAIN.EXE file offset 0x047536, first 8 B/R/G entries",
            "record_index": record_index,
            "asm_reference": "MAIN.EXE sub_13F8C reads index*0x438 and draws 8 tiles by 0x2D pixels",
        }
        (directory / f"{stem}.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )

    print(f"{relative}: {count} uncompressed 64x45 menu/item images")
    return count


def extract_pack_archive(source: Path, input_root: Path, output_root: Path) -> int:
    data = source.read_bytes()
    relative = source.relative_to(input_root)
    directory = output_root / relative
    directory.mkdir(parents=True, exist_ok=True)
    starts = [sector * 0x200 for sector in PACK_SECTORS]
    ends = starts[1:] + [len(data)]

    for record_index, (start, end) in enumerate(zip(starts, ends)):
        if start >= len(data) or end > len(data):
            raise DecodeError(f"PACK.NB5 sector 0x{PACK_SECTORS[record_index]:03X} is outside the file")
        width, height, planar, indices, stream_end = decode_slogo_image(data, start, end)
        stem = f"{start:06x}"
        block = data[start:end]
        (directory / f"{stem}.cmp.jpn.bin").write_bytes(block)
        (directory / f"{stem}.pln.jpn.bin").write_bytes(planar)
        (directory / f"{stem}.idx.jpn.bin").write_bytes(indices)
        save_png(directory / f"{stem}.jpn.png", indices, width, height, MAIN_PALETTE_00_8)
        metadata = {
            "source": relative.as_posix(),
            "offset": f"0x{start:06X}",
            "original_size": len(block),
            "encoded_size": None,
            "stored_size": None,
            "padding_byte": None,
            "compression": "grpdrv-lz",
            "width": width,
            "height": height,
            "planes": 3,
            "plane_order": "BRG",
            "planar_layout": "interleaved",
            "bit_order": "msb-first",
            "stride": width // 8,
            "palette": [f"#{red:02X}{green:02X}{blue:02X}" for red, green, blue in MAIN_PALETTE_00_8],
            "palette_source": "MAIN.EXE file offset 0x047536, palette used around sub_11460(0x0F)",
            "record_index": record_index,
            "sector": f"0x{PACK_SECTORS[record_index]:03X}",
            "header_size": 4,
            "compressed_stream_size": stream_end - start,
            "asm_reference": "MAIN.EXE sub_13EA8 reads sector*0x200 and draws via GRPDRVEX AH=19h",
        }
        (directory / f"{stem}.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )

    print(f"{relative}: {len(PACK_SECTORS)} compressed GRPDRV images")
    return len(PACK_SECTORS)


def extract_graph_keypad(source: Path, input_root: Path, output_root: Path) -> int:
    """Extract the keypad, including its numeric and Japanese label buttons."""
    data = source.read_bytes()
    start = GRAPH_KEYPAD_OFFSET
    end = start + GRAPH_KEYPAD_SIZE
    if end > len(data):
        raise DecodeError("GRAPH.NB5 keypad block at 0x00585E is outside the file")

    relative = source.relative_to(input_root)
    directory = output_root / relative
    directory.mkdir(parents=True, exist_ok=True)
    planar = data[start:end]
    indices = decode_interleaved_planar(planar, GRAPH_KEYPAD_WIDTH, GRAPH_KEYPAD_HEIGHT, 3)
    stem = f"{start:06x}"
    (directory / f"{stem}.pln.jpn.bin").write_bytes(planar)
    (directory / f"{stem}.idx.jpn.bin").write_bytes(indices)
    save_png(directory / f"{stem}.jpn.png", indices, GRAPH_KEYPAD_WIDTH, GRAPH_KEYPAD_HEIGHT, GRAPH_KEYPAD_PALETTE_8)
    metadata = {
        "source": relative.as_posix(),
        "offset": f"0x{start:06X}",
        "original_size": GRAPH_KEYPAD_SIZE,
        "encoded_size": None,
        "stored_size": None,
        "padding_byte": None,
        "compression": "none",
        "width": GRAPH_KEYPAD_WIDTH,
        "height": GRAPH_KEYPAD_HEIGHT,
        "planes": 3,
        "plane_order": "BRG",
        "planar_layout": "interleaved",
        "bit_order": "msb-first",
        "stride": GRAPH_KEYPAD_WIDTH // 8,
        "palette": [f"#{red:02X}{green:02X}{blue:02X}" for red, green, blue in GRAPH_KEYPAD_PALETTE_8],
        "palette_source": "workspace5 capture/main_002.raw1.png, rectangle (528,46,632,146)",
        "unused_palette_indices": [4],
        "unknown_palette_indices": [4],
        "record_index": 0,
        "header_size": 0,
        "asm_reference": "MAIN.EXE sub_3AE30 copies 0x0F3C bytes from banked 0x1BE28 via sub_1482A; "
        "sub_142EE draws 13 tiles by 100 pixels",
    }
    (directory / f"{stem}.meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\r\n",
    )
    print(f"{relative}: 1 uncompressed 104x100 keypad image")
    return 1


def extract_portrait_archive(source: Path, input_root: Path, output_root: Path) -> int:
    data = source.read_bytes()
    expected_count = PORTRAIT_FILES[source.name.upper()]
    starts = [
        position for position in range(0, len(data) - 3, 4) if data[position : position + 4] == PORTRAIT_SIGNATURE
    ]
    if len(starts) != expected_count:
        raise DecodeError(f"found {len(starts)} aligned portrait headers, expected {expected_count}")

    relative = source.relative_to(input_root)
    directory = output_root / relative
    directory.mkdir(parents=True, exist_ok=True)
    ends = starts[1:] + [len(data)]
    for record_index, (start, end) in enumerate(zip(starts, ends)):
        width, height, indices, stream_end = decode_portrait(data, start)
        if stream_end > end:
            raise DecodeError(f"record {record_index} overlaps the next record")
        if any(data[stream_end:end]):
            raise DecodeError(f"record {record_index} has nonzero trailing data")

        stem = f"{start:06x}"
        block = data[start:end]
        planar = encode_interleaved_planar(indices, width, height, 3)
        (directory / f"{stem}.cmp.jpn.bin").write_bytes(block)
        (directory / f"{stem}.pln.jpn.bin").write_bytes(planar)
        (directory / f"{stem}.idx.jpn.bin").write_bytes(indices)
        save_png(
            directory / f"{stem}.jpn.png",
            indices,
            width,
            height,
            MAIN_PALETTE_00_8,
        )
        metadata = {
            "source": relative.as_posix(),
            "offset": f"0x{start:06X}",
            "original_size": len(block),
            "encoded_size": None,
            "stored_size": None,
            "padding_byte": None,
            "compression": "nb5-portrait-rle",
            "width": width,
            "height": height,
            "planes": 3,
            "plane_order": "BRG",
            "planar_layout": "interleaved",
            "bit_order": "msb-first",
            "stride": width // 8,
            "palette": [f"#{red:02X}{green:02X}{blue:02X}" for red, green, blue in MAIN_PALETTE_00_8],
            "palette_source": "MAIN.EXE file offset 0x047536, first 8 B/R/G entries",
            "record_index": record_index,
            "header_size": 4,
            "compressed_stream_size": stream_end - start,
        }
        (directory / f"{stem}.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )

    print(f"{relative}: {len(starts)} compressed portraits")
    return len(starts)


def extract_kanji(source: Path, input_root: Path, output_root: Path) -> int:
    data = source.read_bytes()
    glyph_size = 32
    if len(data) % glyph_size:
        raise DecodeError("KANJI.NB5 size is not divisible by 32")
    relative = source.relative_to(input_root)
    directory = output_root / relative
    directory.mkdir(parents=True, exist_ok=True)
    count = len(data) // glyph_size

    for index in range(count):
        offset = index * glyph_size
        planar = data[offset : offset + glyph_size]
        indices = bytearray(16 * 16)
        for y in range(16):
            for x_byte in range(2):
                value = planar[y * 2 + x_byte]
                for bit in range(8):
                    if value & (0x80 >> bit):
                        indices[y * 16 + x_byte * 8 + bit] = 1
        stem = f"{offset:06x}"
        (directory / f"{stem}.pln.jpn.bin").write_bytes(planar)
        (directory / f"{stem}.idx.jpn.bin").write_bytes(indices)
        save_png(
            directory / f"{stem}.jpn.png",
            bytes(indices),
            16,
            16,
            [PC98_PALETTE_8[0], PC98_PALETTE_8[7]],
        )
        metadata = {
            "source": relative.as_posix(),
            "offset": f"0x{offset:06X}",
            "original_size": glyph_size,
            "encoded_size": None,
            "stored_size": None,
            "padding_byte": None,
            "compression": "none",
            "width": 16,
            "height": 16,
            "planes": 1,
            "plane_order": "mask",
            "planar_layout": "plane-major-row",
            "bit_order": "msb-first",
            "stride": 2,
            "palette": "monochrome-mask",
            "record_index": index,
        }
        (directory / f"{stem}.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )
    print(f"{relative}: {count} uncompressed 16x16 glyphs")
    return count


def remove_intermediate_outputs(output_directories: list[Path]) -> int:
    """Keep each source-stage raw block plus its final PNG and metadata."""
    removed = 0
    for directory in output_directories:
        for path in directory.glob("*.idx.jpn.bin"):
            path.unlink()
            removed += 1
        for path in directory.glob("*.pln.jpn.bin"):
            stem = path.name.removesuffix(".pln.jpn.bin")
            metadata_path = path.with_name(f"{stem}.meta.json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata["compression"] != "none":
                path.unlink()
                removed += 1
        for path in directory.glob("*.cmp.jpn.bin"):
            stem = path.name.removesuffix(".cmp.jpn.bin")
            metadata_path = path.with_name(f"{stem}.meta.json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata["compression"] == "none":
                path.unlink()
                removed += 1
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract image resources from jpn-pc98 into image-pc98.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("c:/work_han/workspace5"),
        help="workspace containing jpn-pc98 and image-pc98 (default: c:/work_han/workspace5)",
    )
    parser.add_argument(
        "--all-artifacts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="also keep planar and indexed intermediate artifacts (default: no-all-artifacts)",
    )
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    input_root = workspace / "jpn-pc98"
    output_root = workspace / "image-pc98"

    total = 0
    output_directories = []
    sopen = input_root / "SOPEN.NB5"
    if not sopen.is_file():
        raise SystemExit(f"missing source file: {sopen}")
    total += extract_sopen_archive(sopen, input_root, output_root)
    output_directories.append(output_root / sopen.name)
    nkao = input_root / "NKAO.NB5"
    if not nkao.is_file():
        raise SystemExit(f"missing source file: {nkao}")
    total += extract_nkao_archive(nkao, input_root, output_root)
    output_directories.append(output_root / nkao.name)
    graph = input_root / "GRAPH.NB5"
    if not graph.is_file():
        raise SystemExit(f"missing source file: {graph}")
    total += extract_graph_keypad(graph, input_root, output_root)
    output_directories.append(output_root / graph.name)
    # slogo = input_root / "SLOGO.NB5"
    # if not slogo.is_file():
    #     raise SystemExit(f"missing source file: {slogo}")
    # total += extract_slogo(slogo, input_root, output_root)
    # output_directories.append(output_root / slogo.name)
    # item = input_root / "ITEM.NB5"
    # if not item.is_file():
    #     raise SystemExit(f"missing source file: {item}")
    # total += extract_item_archive(item, input_root, output_root)
    # output_directories.append(output_root / item.name)
    # pack = input_root / "PACK.NB5"
    # if not pack.is_file():
    #     raise SystemExit(f"missing source file: {pack}")
    # total += extract_pack_archive(pack, input_root, output_root)
    # output_directories.append(output_root / pack.name)
    # for filename in PORTRAIT_FILES:
    #     source = input_root / filename
    #     if not source.is_file():
    #         raise SystemExit(f"missing source file: {source}")
    #     total += extract_portrait_archive(source, input_root, output_root)
    #     output_directories.append(output_root / filename)
    # kanji = input_root / "KANJI.NB5"
    # if not kanji.is_file():
    #     raise SystemExit(f"missing source file: {kanji}")
    # total += extract_kanji(kanji, input_root, output_root)
    # output_directories.append(output_root / kanji.name)
    if not args.all_artifacts:
        removed = remove_intermediate_outputs(output_directories)
        print(f"removed {removed} intermediate binary files")
    print(f"wrote {total} images below {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
