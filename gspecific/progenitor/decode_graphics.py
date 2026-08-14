#!/usr/bin/env python3
"""Extract and decode image resources used by workspace0.

The format and decompressor are reconstructed from OPEN.EXE.asm,
END.EXE.asm, and MAIN.EXE.asm.  NPK files contain NPK016 images, while
KAO.LZW contains LS11-compressed 64x80 3bpp portraits and PUT.DAT contains
uncompressed fonts and UI parts.
"""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw


SIGNATURE = b"NPK016"
HEADER_SIZE = 0x30
RING_SIZE = 0x640
RING_ROW_STRIDE = 0x140
LS11_SIGNATURE = b"LS11"
LS11_TABLE_OFFSET = 0x10
LS11_TABLE_SIZE = 0x100
LS11_RECORD_TABLE_OFFSET = 0x110
LS11_RECORD_SIZE = 0x0C
KAO_WIDTH = 64
KAO_HEIGHT = 80
KAO_PLANES = 3
KAO_PLANAR_SIZE = KAO_WIDTH * KAO_HEIGHT * KAO_PLANES // 8
NAME_BMD_WIDTH = 64
NAME_BMD_HEIGHT = 24
NAME_BMD_PLANES = 3
NAME_BMD_RECORD_SIZE = NAME_BMD_WIDTH * NAME_BMD_HEIGHT * NAME_BMD_PLANES // 8
OPENING_WIDTH = 640
OPENING_HEIGHT = 400
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
PC98_PALETTE_16 = PC98_PALETTE_8 + [
    (0x80, 0x80, 0x80),
    (0x80, 0x80, 0xFF),
    (0xFF, 0x80, 0x80),
    (0xFF, 0x80, 0xFF),
    (0x80, 0xFF, 0x80),
    (0x80, 0xFF, 0xFF),
    (0xFF, 0xFF, 0x80),
    (0xFF, 0xFF, 0xFF),
]


class NpkError(ValueError):
    pass


class Ls11Error(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    offset: int
    end: int
    width: int
    height: int
    palette_words: tuple[int, ...]
    block: bytes

    @property
    def payload(self) -> bytes:
        return self.block[HEADER_SIZE:]


def detect_table(data: bytes) -> tuple[str, list[int]]:
    """Return the byte order and validated entry offsets."""
    candidates: list[tuple[str, list[int]]] = []
    for byte_order in ("little", "big"):
        first = int.from_bytes(data[:4], byte_order)
        if first < 4 or first > min(len(data), 0x10000) or first % 4:
            continue
        offsets = [int.from_bytes(data[pos : pos + 4], byte_order) for pos in range(0, first, 4)]
        if offsets and offsets[0] == first and offsets == sorted(offsets) and offsets[-1] < len(data):
            candidates.append((byte_order, offsets))
    if len(candidates) != 1:
        raise NpkError(f"cannot determine NPK table byte order ({len(candidates)} matches)")
    return candidates[0]


def parse_entries(data: bytes, offsets: list[int]) -> list[Entry]:
    entries: list[Entry] = []
    ends = offsets[1:] + [len(data)]
    for offset, end in zip(offsets, ends):
        if end < offset or end - offset < HEADER_SIZE:
            continue
        block = data[offset:end]
        if block[:6] != SIGNATURE:
            continue
        width, height = struct.unpack_from("<HH", block, 0x0C)
        if not width or not height:
            raise NpkError(f"invalid dimensions at 0x{offset:06x}: {width}x{height}")
        palette_words = struct.unpack_from("<16H", block, 0x10)
        entries.append(Entry(offset, end, width, height, palette_words, block))
    return entries


def decompress(payload: bytes, width: int, height: int) -> bytes:
    """Decode the sub_1656B/sub_16726 LZ stream to packed source words."""
    words_per_row = (width + 3) // 4
    ring = bytearray(RING_SIZE)
    source_pos = 0
    ring_row = 0
    control = 0
    control_bits = 0
    packed = bytearray()

    def read_byte() -> int:
        nonlocal source_pos
        if source_pos >= len(payload):
            raise NpkError("compressed stream ended early")
        value = payload[source_pos]
        source_pos += 1
        return value

    for _ in range(height):
        write_pos = ring_row
        produced = 0
        row = bytearray()
        while produced < words_per_row:
            if not control_bits:
                control = read_byte()
                control_bits = 8
            is_backref = control & 1
            control >>= 1
            control_bits -= 1

            if not is_backref:
                word = bytes((read_byte(), read_byte()))
                count = 1
                for value in word:
                    ring[write_pos % RING_SIZE] = value
                    write_pos += 1
                row.extend(word)
            else:
                command = read_byte()
                count = (command & 0x1F) + 1
                selector = ((command >> 5) & 3) + 1
                distance = selector * (RING_ROW_STRIDE if command & 0x80 else 2)
                read_pos = (write_pos - distance) % RING_SIZE
                for _ in range(count * 2):
                    value = ring[read_pos % RING_SIZE]
                    read_pos += 1
                    ring[write_pos % RING_SIZE] = value
                    write_pos += 1
                    row.append(value)

            produced += count
            if produced > words_per_row:
                raise NpkError(f"LZ command crosses a row boundary ({produced}>{words_per_row})")

        packed.extend(row)
        ring_row = (ring_row + RING_ROW_STRIDE) % RING_SIZE
    return bytes(packed)


def packed_to_indices(packed: bytes, width: int, height: int) -> bytes:
    """Convert each four-pixel B/R/G/I bitplane word to row-major indices."""
    words_per_row = (width + 3) // 4
    expected = words_per_row * height * 2
    if len(packed) != expected:
        raise NpkError(f"packed size is {len(packed)}, expected {expected}")

    indices = bytearray()
    source_pos = 0
    for _ in range(height):
        row = bytearray()
        for _ in range(words_per_row):
            green_intensity, blue_red = packed[source_pos : source_pos + 2]
            source_pos += 2
            masks = (
                blue_red & 0x0F,
                blue_red >> 4,
                green_intensity & 0x0F,
                green_intensity >> 4,
            )
            for bit in (3, 2, 1, 0):
                index = sum(((mask >> bit) & 1) << plane for plane, mask in enumerate(masks))
                row.append(index)
        indices.extend(row[:width])
    return bytes(indices)


def palette_rgb(words: tuple[int, ...]) -> list[tuple[int, int, int]]:
    """Decode the PC-98 G/R/B nibble palette stored in an NPK016 header."""
    return [(((word >> 4) & 0xF) * 17, ((word >> 8) & 0xF) * 17, (word & 0xF) * 17) for word in words]


def write_entry(
    entry: Entry,
    source_relative: Path,
    output_directory: Path,
    table_byte_order: str,
) -> None:
    stem = f"{entry.offset:06x}"
    packed = decompress(entry.payload, entry.width, entry.height)
    indices = packed_to_indices(packed, entry.width, entry.height)
    palette = palette_rgb(entry.palette_words)

    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / f"{stem}.cmp.jpn.bin").write_bytes(entry.block)
    (output_directory / f"{stem}.idx.jpn.bin").write_bytes(indices)

    rgb = bytes(component for index in indices for component in palette[index])
    image = Image.frombytes("RGB", (entry.width, entry.height), rgb)
    image.save(output_directory / f"{stem}.jpn.png")

    metadata = {
        "source": source_relative.as_posix(),
        "offset": f"0x{entry.offset:06X}",
        "original_size": len(entry.block),
        "encoded_size": None,
        "stored_size": None,
        "padding_byte": None,
        "compression": "npk016-lz",
        "width": entry.width,
        "height": entry.height,
        "planes": 4,
        "plane_order": "BRGI",
        "planar_layout": None,
        "packed_layout": "four-pixel-bitplane-words",
        "bit_order": "msb-first",
        "stride": (entry.width + 3) // 4 * 2,
        "palette": [f"#{red:02X}{green:02X}{blue:02X}" for red, green, blue in palette],
        "container_table_byte_order": table_byte_order,
        "header_size": HEADER_SIZE,
    }
    (output_directory / f"{stem}.meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def row_plane_major_to_indices_4bpp(planar: bytes, width: int, height: int) -> bytes:
    """Decode the OPEN.EXE row/plane/pixel layout used by sub_13C26."""
    if width % 8:
        raise NpkError(f"4bpp planar width is not byte-aligned: {width}")
    stride = width // 8
    expected = stride * height * 4
    if len(planar) != expected:
        raise NpkError(f"4bpp planar size is {len(planar)}, expected {expected}")

    indices = bytearray(width * height)
    for y in range(height):
        row_offset = y * stride * 4
        for plane in range(4):
            plane_offset = row_offset + plane * stride
            for x_byte in range(stride):
                value = planar[plane_offset + x_byte]
                pixel_offset = y * width + x_byte * 8
                for bit in range(8):
                    if value & (0x80 >> bit):
                        indices[pixel_offset + bit] |= 1 << plane
    return bytes(indices)


def mask_1bpp_to_indices(source: bytes, width: int, height: int, color: int) -> bytes:
    """Convert an OPEN.NPK monochrome layer to natural-size color indices."""
    if width % 8 or len(source) != width // 8 * height:
        raise NpkError(f"invalid 1bpp opening block ({width}x{height})")
    stride = width // 8
    indices = bytearray(width * height)
    for source_y in range(height):
        for source_x in range(width):
            if source[source_y * stride + source_x // 8] & (0x80 >> (source_x & 7)):
                indices[source_y * width + source_x] = color
    return bytes(indices)


def write_opening_layer(
    source_bytes: bytes,
    indices: bytes,
    palette: list[tuple[int, int, int]],
    output_directory: Path,
    source_offset: int,
    metadata: dict[str, object],
) -> None:
    stem = f"{source_offset:06x}"
    (output_directory / f"{stem}.pln.jpn.bin").write_bytes(source_bytes)
    (output_directory / f"{stem}.idx.jpn.bin").write_bytes(indices)
    rgba = bytes(component for index in indices for component in (*palette[index], 255 if index else 0))
    Image.frombytes("RGBA", (int(metadata["width"]), int(metadata["height"])), rgba).save(
        output_directory / f"{stem}.jpn.png",
    )
    (output_directory / f"{stem}.meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def extract_opening_layers(
    data: bytes,
    offsets: list[int],
    entries: list[Entry],
    source_relative: Path,
    output_directory: Path,
) -> int:
    """Extract the individual layers consumed by OPEN.EXE before composition."""
    if len(offsets) < 3 or len(entries) < 1:
        raise NpkError("OPEN.NPK is missing opening layer records")

    # Remove files produced by the older composite-screen implementation so a
    # rerun cannot leave them looking like current extractor output.
    for screen_index in range(2):
        for suffix in ("idx.jpn.bin", "jpn.png", "meta.json"):
            (output_directory / f"opening_{screen_index:03d}.{suffix}").unlink(missing_ok=True)
    for old_offset in (0x000040, 0x000BA0, 0x000E10, 0x001470, 0x004941):
        for suffix in (
            "msk.jpn.bin",
            "pln.jpn.bin",
            "idx.jpn.bin",
            "jpn.png",
            "meta.json",
        ):
            (output_directory / f"layer_{old_offset:06x}.{suffix}").unlink(missing_ok=True)

    # sub_1BAB6 uses record 0 as four independent, tightly packed 1bpp masks.
    # The x/y coordinates are destinations only and are retained as metadata;
    # each PNG remains at its natural pre-composition size.
    first_block = data[offsets[0] : offsets[1]]
    if len(first_block) != 0x18E0:
        raise NpkError(f"unexpected OPEN.NPK record 0 size: 0x{len(first_block):X}")
    startup_palette = PC98_PALETTE_8 + [(0, 0, 0)] * 8
    startup_palette[7] = (255, 239, 223)
    mask_specs = (
        (0x0000, 208, 112, 216, 96, 2, "koei-logo"),
        (0x0B60, 208, 24, 216, 224, 7, "koei-caption"),
        (0x0DD0, 272, 48, 184, 144, 7, "fukuzawa-title"),
        (0x1430, 400, 24, 128, 224, 7, "fukuzawa-caption"),
    )
    for relative_offset, width, height, x, y, color, category in mask_specs:
        size = width // 8 * height
        source_offset = offsets[0] + relative_offset
        source_bytes = first_block[relative_offset : relative_offset + size]
        indices = mask_1bpp_to_indices(source_bytes, width, height, color)
        write_opening_layer(
            source_bytes,
            indices,
            startup_palette,
            output_directory,
            source_offset,
            {
                "source": source_relative.as_posix(),
                "offset": f"0x{source_offset:06X}",
                "record_offset": f"0x{offsets[0]:06X}",
                "original_size": len(source_bytes),
                "encoded_size": None,
                "stored_size": None,
                "padding_byte": None,
                "compression": "none",
                "category": category,
                "width": width,
                "height": height,
                "planes": 1,
                "plane_order": "mask",
                "planar_layout": "row-major",
                "bit_order": "msb-first",
                "stride": width // 8,
                "draw_color_index": color,
                "palette": "OPEN.EXE startup palette",
                "composition_destination": {"x": x, "y": y},
                "alpha": "index 0 is transparent",
                "assembly_routine": "OPEN.EXE sub_1BAB6",
            },
        )

    # Record 1 is already emitted as the standalone 001920 NPK016 background.
    # sub_1BA06 draws record 2 over it as one 400x144, four-plane layer.
    background = next((entry for entry in entries if entry.offset == offsets[1]), None)
    if background is None or (
        background.width,
        background.height,
    ) != (OPENING_WIDTH, OPENING_HEIGHT):
        raise NpkError("OPEN.NPK record 1 is not the 640x400 opening background")
    logo_block = data[offsets[2] : offsets[3] if len(offsets) > 3 else len(data)]
    logo_indices = row_plane_major_to_indices_4bpp(logo_block, 400, 144)
    palette = palette_rgb(background.palette_words)
    write_opening_layer(
        logo_block,
        logo_indices,
        palette,
        output_directory,
        offsets[2],
        {
            "source": source_relative.as_posix(),
            "offset": f"0x{offsets[2]:06X}",
            "background_layer": f"{background.offset:06x}.jpn.png",
            "original_size": len(logo_block),
            "encoded_size": None,
            "stored_size": None,
            "padding_byte": None,
            "compression": "none",
            "category": "progenitor-logo",
            "width": 400,
            "height": 144,
            "planes": 4,
            "plane_order": "BRGI",
            "planar_layout": "row-plane-major",
            "bit_order": "msb-first",
            "stride": 50,
            "composition_destination": {"x": 120, "y": 128},
            "alpha": "index 0 is transparent",
            "assembly_routine": "OPEN.EXE sub_1BA06/sub_13C92",
            "palette": [f"#{red:02X}{green:02X}{blue:02X}" for red, green, blue in palette],
        },
    )
    return len(mask_specs) + 1


def extract_archive(source: Path, input_root: Path, output_root: Path) -> int:
    data = source.read_bytes()
    table_byte_order, offsets = detect_table(data)
    entries = parse_entries(data, offsets)
    if not entries:
        raise NpkError("no NPK016 image entries found")

    relative = source.relative_to(input_root)
    output_directory = output_root / relative
    for entry in entries:
        write_entry(entry, relative, output_directory, table_byte_order)
    count = len(entries)
    if source.name.upper() == "OPEN.NPK":
        count += extract_opening_layers(data, offsets, entries, relative, output_directory)
    print(f"{relative}: {count} images ({table_byte_order}-endian table)")
    return count


class BitReader:
    def __init__(self, data: bytes):
        self.data = data
        self.byte_pos = 0
        self.value = 0
        self.bits_left = 0

    def read_bit(self) -> int:
        if not self.bits_left:
            if self.byte_pos >= len(self.data):
                raise Ls11Error("compressed bit stream ended early")
            self.value = self.data[self.byte_pos]
            self.byte_pos += 1
            self.bits_left = 8
        bit = (self.value >> 7) & 1
        self.value = (self.value << 1) & 0xFF
        self.bits_left -= 1
        return bit

    def read_code(self) -> int:
        prefix = 0
        width = 0
        while True:
            width += 1
            bit = self.read_bit()
            prefix = prefix * 2 + bit
            if not bit:
                break
        suffix = 0
        for _ in range(width):
            suffix = suffix * 2 + self.read_bit()
        return prefix + suffix


def decompress_ls11(payload: bytes, literal_table: bytes, output_size: int, stored_size: int) -> bytes:
    if stored_size == output_size:
        if len(payload) < output_size:
            raise Ls11Error("uncompressed record ended early")
        return payload[:output_size]

    reader = BitReader(payload)
    output = bytearray()
    while len(output) < output_size:
        code = reader.read_code()
        if code < 0x100:
            output.append(literal_table[code])
            continue

        distance = code - 0x100
        length = reader.read_code() + 3
        if not distance or distance > len(output):
            raise Ls11Error(f"invalid back-reference distance {distance} at output {len(output)}")
        for _ in range(length):
            output.append(output[-distance])
            if len(output) == output_size:
                break
    return bytes(output)


def row_plane_major_to_indices(planar: bytes, width: int, height: int, planes: int) -> bytes:
    stride = width // 8
    expected = stride * height * planes
    if width % 8 or len(planar) != expected:
        raise Ls11Error(f"planar size is {len(planar)}, expected {expected}")
    indices = bytearray(width * height)
    for y in range(height):
        row_offset = y * stride * planes
        for plane in range(planes):
            plane_offset = row_offset + plane * stride
            for x_byte in range(stride):
                value = planar[plane_offset + x_byte]
                pixel_offset = y * width + x_byte * 8
                for bit in range(8):
                    if value & (0x80 >> bit):
                        indices[pixel_offset + bit] |= 1 << plane
    return bytes(indices)


def write_put_image(
    data: bytes,
    source_relative: Path,
    output_directory: Path,
    offset: int,
    width: int,
    height: int,
    planes: int,
    category: str,
) -> None:
    size = width * height * planes // 8
    end = offset + size
    if width % 8 or end > len(data):
        raise ValueError(f"invalid PUT.DAT block at 0x{offset:06x}")
    planar = data[offset:end]
    indices = row_plane_major_to_indices(planar, width, height, planes)
    palette = PC98_PALETTE_8 if planes == 3 else [PC98_PALETTE_8[0], PC98_PALETTE_8[7]]
    stem = f"{offset:06x}"

    (output_directory / f"{stem}.pln.jpn.bin").write_bytes(planar)
    (output_directory / f"{stem}.idx.jpn.bin").write_bytes(indices)
    rgb = bytes(component for index in indices for component in palette[index])
    Image.frombytes("RGB", (width, height), rgb).save(output_directory / f"{stem}.jpn.png")
    metadata = {
        "source": source_relative.as_posix(),
        "offset": f"0x{offset:06X}",
        "original_size": size,
        "encoded_size": None,
        "stored_size": None,
        "padding_byte": None,
        "compression": "none",
        "width": width,
        "height": height,
        "planes": planes,
        "plane_order": "BRG" if planes == 3 else "mask",
        "planar_layout": "row-plane-major",
        "bit_order": "msb-first",
        "stride": width // 8,
        "palette": "pc98-default-8" if planes == 3 else "monochrome-mask",
        "category": category,
    }
    (output_directory / f"{stem}.meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def extract_put(source: Path, input_root: Path, output_root: Path) -> int:
    """Extract PUT.DAT blocks whose boundaries are explicit in MAIN.EXE."""
    data = source.read_bytes()
    relative = source.relative_to(input_root)
    output_directory = output_root / relative
    output_directory.mkdir(parents=True, exist_ok=True)

    specs: list[tuple[int, int, int, int, str]] = []
    specs.extend((index * 0x20, 16, 16, 1, "digit-font-16x16") for index in range(10))
    specs.extend((0x140 + index * 0x10, 8, 16, 1, "digit-font-8x16") for index in range(10))
    specs.extend((0x1F0 + index * 0x0A, 8, 10, 1, "digit-font-8x10") for index in range(10))
    specs.extend((start + index * 0x60, 16, 16, 3, "ui-part-16x16") for start in (0x254, 0x2BF4) for index in range(5))
    specs.extend((0x2DD4 + index * 0x18, 8, 8, 3, "window-tile-8x8") for index in range(15))
    specs.extend((0x66BC + index * 0xD8, 24, 24, 3, "battle-ui-icon-24x24") for index in range(12))

    for offset, width, height, planes, category in specs:
        write_put_image(
            data,
            relative,
            output_directory,
            offset,
            width,
            height,
            planes,
            category,
        )
    print(f"{relative}: {len(specs)} uncompressed font/UI images")
    return len(specs)


def extract_name_bmd(source: Path, input_root: Path, output_root: Path) -> int:
    """Extract NAME.BMD 64x24 3bpp location/facility label graphics."""
    data = source.read_bytes()
    if len(data) % NAME_BMD_RECORD_SIZE:
        raise ValueError(f"NAME.BMD size is not 0x{NAME_BMD_RECORD_SIZE:X} aligned: 0x{len(data):X}")
    relative = source.relative_to(input_root)
    output_directory = output_root / relative
    output_directory.mkdir(parents=True, exist_ok=True)

    count = len(data) // NAME_BMD_RECORD_SIZE
    images: list[Image.Image] = []
    for record_index in range(count):
        offset = record_index * NAME_BMD_RECORD_SIZE
        planar = data[offset : offset + NAME_BMD_RECORD_SIZE]
        indices = row_plane_major_to_indices(planar, NAME_BMD_WIDTH, NAME_BMD_HEIGHT, NAME_BMD_PLANES)
        stem = f"{offset:06x}"

        (output_directory / f"{stem}.pln.jpn.bin").write_bytes(planar)
        (output_directory / f"{stem}.idx.jpn.bin").write_bytes(indices)
        rgb = indices_to_rgb(indices, PC98_PALETTE_8)
        image = Image.frombytes("RGB", (NAME_BMD_WIDTH, NAME_BMD_HEIGHT), rgb)
        image.save(output_directory / f"{stem}.jpn.png")
        images.append(image)

        metadata = {
            "source": relative.as_posix(),
            "offset": f"0x{offset:06X}",
            "record_index": record_index,
            "original_size": NAME_BMD_RECORD_SIZE,
            "encoded_size": None,
            "stored_size": None,
            "padding_byte": None,
            "compression": "none",
            "category": "name-bmd-location-label",
            "width": NAME_BMD_WIDTH,
            "height": NAME_BMD_HEIGHT,
            "planes": NAME_BMD_PLANES,
            "plane_order": "BRG",
            "planar_layout": "row-plane-major",
            "bit_order": "msb-first",
            "stride": NAME_BMD_WIDTH // 8,
            "palette": "pc98-default-8",
            "record_size": NAME_BMD_RECORD_SIZE,
            "assembly_routine": "MAIN.EXE sub_1D6AC/sub_117DC",
        }
        (output_directory / f"{stem}.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if images:
        columns = min(8, count)
        rows = (count + columns - 1) // columns
        label_height = 12
        padding = 6
        scale = 2
        cell_width = NAME_BMD_WIDTH * scale + padding
        cell_height = NAME_BMD_HEIGHT * scale + label_height + padding
        sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)
        for record_index, image in enumerate(images):
            x = (record_index % columns) * cell_width
            y = (record_index // columns) * cell_height
            offset = record_index * NAME_BMD_RECORD_SIZE
            draw.text((x, y), f"{record_index:02X} {offset:04X}", fill=(0, 0, 0))
            sheet.paste(
                image.resize((NAME_BMD_WIDTH * scale, NAME_BMD_HEIGHT * scale), Image.Resampling.NEAREST),
                (x, y + label_height),
            )
        sheet.save(output_directory / "contact_sheet.png")

    print(f"{relative}: {count} NAME.BMD location/facility labels")
    return count


def extract_btgrp(source: Path, input_root: Path, output_root: Path) -> int:
    """Split BTGRP.DAT table records and decode its object tile sets."""
    data = source.read_bytes()
    table_byte_order, offsets = detect_table(data)
    if table_byte_order != "big":
        raise NpkError(f"unexpected BTGRP.DAT table byte order: {table_byte_order}")
    relative = source.relative_to(input_root)
    output_directory = output_root / relative
    output_directory.mkdir(parents=True, exist_ok=True)

    count = 0
    ends = offsets[1:] + [len(data)]
    for record_index, (offset, end) in enumerate(zip(offsets, ends)):
        block = data[offset:end]
        stem = f"record_{record_index:02d}_{offset:06x}"
        if block == b"END OF BTGRP":
            (output_directory / f"{stem}.txt").write_text(
                block.decode("ascii") + "\n",
                encoding="ascii",
            )
            continue

        (output_directory / f"{stem}.cmp.jpn.bin").write_bytes(block)
        metadata = {
            "source": relative.as_posix(),
            "offset": f"0x{offset:06X}",
            "record_index": record_index,
            "original_size": len(block),
            "encoded_size": None,
            "stored_size": None,
            "padding_byte": None,
            "compression": "unknown-btgrp-record",
            "container_table_byte_order": table_byte_order,
        }
        (output_directory / f"{stem}.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )
        count += 1

        if record_index == 0:
            if len(block) % 8:
                raise NpkError(f"BTGRP.DAT record 0 size is not 8x8 aligned: 0x{len(block):X}")
            for tile_index in range(len(block) // 8):
                tile = block[tile_index * 8 : (tile_index + 1) * 8]
                indices = mask_1bpp_to_indices(tile, 8, 8, 7)
                write_opening_layer(
                    tile,
                    indices,
                    PC98_PALETTE_8,
                    output_directory,
                    offset + tile_index * 8,
                    {
                        "source": relative.as_posix(),
                        "offset": f"0x{offset + tile_index * 8:06X}",
                        "record_offset": f"0x{offset:06X}",
                        "record_index": record_index,
                        "tile_index": tile_index,
                        "original_size": len(tile),
                        "encoded_size": None,
                        "stored_size": None,
                        "padding_byte": None,
                        "compression": "none",
                        "category": "btgrp-8x8-mask",
                        "width": 8,
                        "height": 8,
                        "planes": 1,
                        "plane_order": "mask",
                        "planar_layout": "row-major",
                        "bit_order": "msb-first",
                        "stride": 1,
                        "palette": "pc98-default-8",
                    },
                )
                count += 1
        elif len(block) >= 0x80:
            tile_count = len(block) // 0x80
            if tile_count:
                sheet_columns = min(20, tile_count)
                sheet_rows = (tile_count + sheet_columns - 1) // sheet_columns
                sheet = Image.new("RGB", (sheet_columns * 17, sheet_rows * 17), (0x20, 0x20, 0x20))
                for tile_index in range(tile_count):
                    tile = block[tile_index * 0x80 : (tile_index + 1) * 0x80]
                    indices = decode_btgrp_16x16_tile(tile)
                    tile_image = Image.frombytes(
                        "RGB",
                        (16, 16),
                        indices_to_rgb(indices, PC98_PALETTE_16),
                    )
                    sheet.paste(tile_image, ((tile_index % sheet_columns) * 17, (tile_index // sheet_columns) * 17))
                sheet.save(output_directory / f"{stem}.tile16.jpn.png")

    print(f"{relative}: {count} BTGRP records/tiles ({table_byte_order}-endian table)")
    return count


def decode_btgrp_16x16_tile(tile: bytes) -> bytes:
    if len(tile) != 0x80:
        raise NpkError(f"BTGRP 16x16 tile size is 0x{len(tile):X}, expected 0x80")
    indices = bytearray(16 * 16)
    for y in range(16):
        words = [
            int.from_bytes(tile[plane * 0x20 + y * 2 : plane * 0x20 + y * 2 + 2], "little")
            for plane in range(4)
        ]
        for x in range(16):
            bit = 15 - x
            indices[y * 16 + x] = sum(((words[plane] >> bit) & 1) << plane for plane in range(4))
    return bytes(indices)


def indices_to_rgb(indices: bytes, palette: list[tuple[int, int, int]]) -> bytes:
    rgb = bytearray()
    for index in indices:
        rgb.extend(palette[index])
    return bytes(rgb)


def indices_to_rgba(indices: bytes, palette: list[tuple[int, int, int]], transparent_index: int = 0) -> bytes:
    rgba = bytearray()
    for index in indices:
        if index == transparent_index:
            rgba.extend((0, 0, 0, 0))
        else:
            rgba.extend((*palette[index], 255))
    return bytes(rgba)


def load_btgrp_16x16_records(source: Path) -> list[list[bytes]]:
    data = source.read_bytes()
    table_byte_order, offsets = detect_table(data)
    if table_byte_order != "big" or len(offsets) < 2:
        raise NpkError("BTGRP.DAT does not have the expected big-endian table")
    records: list[list[bytes]] = []
    for offset, end in zip(offsets, offsets[1:] + [len(data)]):
        block = data[offset:end]
        records.append([block[index : index + 0x80] for index in range(0, len(block) - len(block) % 0x80, 0x80)])
    return records


def load_btgrp_mask_tiles(source: Path) -> list[bytes]:
    data = source.read_bytes()
    table_byte_order, offsets = detect_table(data)
    if table_byte_order != "big" or len(offsets) < 2:
        raise NpkError("BTGRP.DAT does not have the expected big-endian table")
    block = data[offsets[0] : offsets[1]]
    if len(block) % 8:
        raise NpkError(f"BTGRP.DAT record 0 size is not 8x8 aligned: 0x{len(block):X}")
    return [block[index : index + 8] for index in range(0, len(block), 8)]


def render_bgobj_record(record: bytes, tiles: list[bytes]) -> tuple[int, int, bytes, bytes]:
    if len(record) != 0x48:
        raise NpkError(f"BGOBJ.DAT record size is 0x{len(record):X}, expected 0x48")
    width_tiles = record[1]
    height_tiles = record[3]
    base_tile = record[6]
    width = max(1, width_tiles) * 16
    height = max(1, height_tiles) * 16
    indices = bytearray(width * height)
    for row in range(height_tiles):
        for column in range(width_tiles):
            map_index = row * 8 + column
            tile_value = record[8 + map_index]
            if tile_value == 0xFF:
                continue
            tile_index = (tile_value & 0x7F) + base_tile
            if tile_index >= len(tiles):
                raise NpkError(f"BGOBJ.DAT references BTGRP tile 0x{tile_index:02X}")
            tile_indices = decode_btgrp_16x16_tile(tiles[tile_index])
            for y in range(16):
                dest = (row * 16 + y) * width + column * 16
                src = y * 16
                indices[dest : dest + 16] = tile_indices[src : src + 16]
    return width, height, bytes(indices), indices_to_rgba(bytes(indices), PC98_PALETTE_16)


def render_bgobj_map_preview(record: bytes, tiles: list[bytes]) -> tuple[bytes, bytes]:
    tile_map = record[8:]
    indices = bytearray(64 * 64)
    for map_index, tile_value in enumerate(tile_map):
        if tile_value == 0xFF:
            continue
        tile_index = tile_value & 0x7F
        if tile_index >= len(tiles):
            raise NpkError(f"BGOBJ.DAT references BTGRP tile 0x{tile_index:02X}")
        color = 2 if tile_value & 0x80 else 7
        tile = tiles[tile_index]
        origin_x = (map_index % 8) * 8
        origin_y = (map_index // 8) * 8
        for y, row in enumerate(tile):
            for x in range(8):
                if row & (0x80 >> x):
                    indices[(origin_y + y) * 64 + origin_x + x] = color

    rgba = bytearray()
    for index in indices:
        if index == 0:
            rgba.extend((0, 0, 0, 0))
        else:
            rgba.extend((*PC98_PALETTE_8[index], 255))
    return bytes(indices), bytes(rgba)


def extract_bgobj(source: Path, input_root: Path, output_root: Path) -> int:
    """Decode BGOBJ.DAT tile-map foreground object definitions."""
    btgrp_source = source.with_name("BTGRP.DAT")
    if not btgrp_source.is_file():
        raise NpkError(f"missing BTGRP.DAT next to {source.name}")
    btgrp_records = load_btgrp_16x16_records(btgrp_source)
    mask_tiles = load_btgrp_mask_tiles(btgrp_source)

    data = source.read_bytes()
    if len(data) % 0x48:
        raise NpkError(f"BGOBJ.DAT size is not 0x48 aligned: 0x{len(data):X}")
    relative = source.relative_to(input_root)
    output_directory = output_root / relative
    output_directory.mkdir(parents=True, exist_ok=True)

    count = 0
    for record_index in range(len(data) // 0x48):
        offset = record_index * 0x48
        record = data[offset : offset + 0x48]
        stem = f"{offset:06x}"
        group_index = offset // 0xA20
        btgrp_record_index = group_index + 6
        if btgrp_record_index >= len(btgrp_records):
            raise NpkError(f"BGOBJ.DAT group {group_index} has no BTGRP record {btgrp_record_index}")
        width, height, indices, rgba = render_bgobj_record(record, btgrp_records[btgrp_record_index])
        preview_indices, preview_rgba = render_bgobj_map_preview(record, mask_tiles)

        (output_directory / f"{stem}.map.jpn.bin").write_bytes(record)
        (output_directory / f"{stem}.idx.jpn.bin").write_bytes(indices)
        Image.frombytes("RGBA", (width, height), rgba).save(output_directory / f"{stem}.jpn.png")
        Image.frombytes("RGBA", (64, 64), preview_rgba).save(output_directory / f"{stem}.map-preview.jpn.png")
        metadata = {
            "source": relative.as_posix(),
            "offset": f"0x{offset:06X}",
            "record_index": record_index,
            "original_size": len(record),
            "encoded_size": None,
            "stored_size": None,
            "padding_byte": None,
            "compression": "none",
            "category": "bgobj-16x16-tilemap",
            "width": width,
            "height": height,
            "planes": 4,
            "tile_width": 16,
            "tile_height": 16,
            "tile_columns": record[1],
            "tile_rows": record[3],
            "tile_base": record[6],
            "group_index": group_index,
            "tile_source": f"BTGRP.DAT record {btgrp_record_index}",
            "record_header": record[:8].hex(),
            "tile_map_offset": 8,
            "tile_map_size": 64,
            "transparent_index": 0,
            "tile_index_rule": "(tile_value & 0x7F) + tile_base, 0xFF is transparent",
            "palette": "pc98-default-16",
        }
        (output_directory / f"{stem}.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )
        count += 1

    print(f"{relative}: {count} BGOBJ tile-map objects")
    return count


def extract_kao(source: Path, input_root: Path, output_root: Path) -> int:
    data = source.read_bytes()
    if data[:4] != LS11_SIGNATURE or len(data) < LS11_RECORD_TABLE_OFFSET + 12:
        raise Ls11Error("not an LS11 archive")
    literal_table = data[LS11_TABLE_OFFSET : LS11_TABLE_OFFSET + LS11_TABLE_SIZE]
    first_data_offset = int.from_bytes(data[LS11_RECORD_TABLE_OFFSET + 8 : LS11_RECORD_TABLE_OFFSET + 12], "big")
    table_size = first_data_offset - LS11_RECORD_TABLE_OFFSET
    record_count = table_size // LS11_RECORD_SIZE
    if record_count <= 0:
        raise Ls11Error("invalid LS11 record table size")

    relative = source.relative_to(input_root)
    output_directory = output_root / relative
    output_directory.mkdir(parents=True, exist_ok=True)
    palette = PC98_PALETTE_8

    for record_index in range(record_count):
        descriptor_offset = LS11_RECORD_TABLE_OFFSET + record_index * LS11_RECORD_SIZE
        stored_size, output_size, source_offset = struct.unpack_from(">III", data, descriptor_offset)
        if output_size != KAO_PLANAR_SIZE:
            raise Ls11Error(f"record {record_index} output size is {output_size}, expected {KAO_PLANAR_SIZE}")
        end = source_offset + stored_size
        if source_offset < first_data_offset or end > len(data):
            raise Ls11Error(f"record {record_index} points outside the archive")
        payload = data[source_offset:end]
        planar = decompress_ls11(payload, literal_table, output_size, stored_size)
        indices = row_plane_major_to_indices(planar, KAO_WIDTH, KAO_HEIGHT, KAO_PLANES)
        stem = f"{source_offset:06x}"
        if stored_size != output_size:
            (output_directory / f"{stem}.cmp.jpn.bin").write_bytes(payload)
        (output_directory / f"{stem}.pln.jpn.bin").write_bytes(planar)
        (output_directory / f"{stem}.idx.jpn.bin").write_bytes(indices)
        rgb = bytes(component for index in indices for component in palette[index])
        Image.frombytes("RGB", (KAO_WIDTH, KAO_HEIGHT), rgb).save(output_directory / f"{stem}.jpn.png")
        metadata = {
            "source": relative.as_posix(),
            "offset": f"0x{source_offset:06X}",
            "original_size": stored_size,
            "encoded_size": None,
            "stored_size": None,
            "padding_byte": None,
            "compression": "ls11" if stored_size != output_size else "none",
            "width": KAO_WIDTH,
            "height": KAO_HEIGHT,
            "planes": KAO_PLANES,
            "plane_order": "BRG",
            "planar_layout": "row-plane-major",
            "bit_order": "msb-first",
            "stride": KAO_WIDTH // 8,
            "palette": "pc98-default-8",
            "record_index": record_index,
            "descriptor_offset": f"0x{descriptor_offset:06X}",
            "decoded_size": output_size,
        }
        (output_directory / f"{stem}.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"{relative}: {record_count} portraits (LS11 records)")
    return record_count


def iter_ls11_records(source: Path) -> tuple[bytes, int, list[tuple[int, int, int, bytes, bytes]]]:
    data = source.read_bytes()
    if data[:4] != LS11_SIGNATURE or len(data) < LS11_RECORD_TABLE_OFFSET + 12:
        raise Ls11Error("not an LS11 archive")
    literal_table = data[LS11_TABLE_OFFSET : LS11_TABLE_OFFSET + LS11_TABLE_SIZE]
    first_data_offset = int.from_bytes(data[LS11_RECORD_TABLE_OFFSET + 8 : LS11_RECORD_TABLE_OFFSET + 12], "big")
    table_size = first_data_offset - LS11_RECORD_TABLE_OFFSET
    record_count = table_size // LS11_RECORD_SIZE
    if record_count <= 0:
        raise Ls11Error("invalid LS11 record table size")

    records: list[tuple[int, int, int, bytes, bytes]] = []
    for record_index in range(record_count):
        descriptor_offset = LS11_RECORD_TABLE_OFFSET + record_index * LS11_RECORD_SIZE
        stored_size, output_size, source_offset = struct.unpack_from(">III", data, descriptor_offset)
        end = source_offset + stored_size
        if source_offset < first_data_offset or end > len(data):
            raise Ls11Error(f"record {record_index} points outside the archive")
        payload = data[source_offset:end]
        decoded = decompress_ls11(payload, literal_table, output_size, stored_size)
        records.append((stored_size, output_size, source_offset, payload, decoded))
    return literal_table, first_data_offset, records


def maybe_decode_lzdata_image(decoded: bytes) -> tuple[int, int, bytes] | None:
    if len(decoded) < 4:
        return None
    width = int.from_bytes(decoded[0:2], "little")
    height = int.from_bytes(decoded[2:4], "little")
    if width <= 0 or height <= 0 or width > 640 or height > 400 or width % 8:
        return None
    planar = decoded[4:]
    if len(planar) != width * height * 4 // 8:
        return None
    return width, height, planar


def extract_lzdata(source: Path, input_root: Path, output_root: Path) -> int:
    """Decode LZDATA.LZW LS11 records and render 4bpp image records."""
    _literal_table, first_data_offset, records = iter_ls11_records(source)
    relative = source.relative_to(input_root)
    output_directory = output_root / relative
    output_directory.mkdir(parents=True, exist_ok=True)

    rendered = 0
    for record_index, (stored_size, output_size, source_offset, payload, decoded) in enumerate(records):
        stem = f"record_{record_index:02d}_{source_offset:06x}"
        if stored_size != output_size:
            (output_directory / f"{stem}.cmp.jpn.bin").write_bytes(payload)
        (output_directory / f"{stem}.bin.jpn.bin").write_bytes(decoded)

        image = maybe_decode_lzdata_image(decoded)
        metadata = {
            "source": relative.as_posix(),
            "offset": f"0x{source_offset:06X}",
            "record_index": record_index,
            "descriptor_offset": f"0x{LS11_RECORD_TABLE_OFFSET + record_index * LS11_RECORD_SIZE:06X}",
            "first_data_offset": f"0x{first_data_offset:06X}",
            "original_size": stored_size,
            "encoded_size": None,
            "stored_size": None,
            "padding_byte": None,
            "compression": "ls11" if stored_size != output_size else "none",
            "decoded_size": output_size,
            "category": "lzdata-record",
        }
        if image is not None:
            width, height, planar = image
            indices = row_plane_major_to_indices(planar, width, height, 4)
            rgba = indices_to_rgba(indices, PC98_PALETTE_16)
            (output_directory / f"{stem}.pln.jpn.bin").write_bytes(planar)
            (output_directory / f"{stem}.idx.jpn.bin").write_bytes(indices)
            Image.frombytes("RGBA", (width, height), rgba).save(output_directory / f"{stem}.jpn.png")
            metadata.update(
                {
                    "category": "lzdata-4bpp-image",
                    "width": width,
                    "height": height,
                    "planes": 4,
                    "plane_order": "BRGI",
                    "planar_layout": "row-plane-major",
                    "bit_order": "msb-first",
                    "stride": width // 8,
                    "header_size": 4,
                    "palette": "pc98-default-16",
                }
            )
            rendered += 1

        (output_directory / f"{stem}.meta.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )

    print(f"{relative}: {len(records)} LS11 records, {rendered} 4bpp images")
    return len(records)


def remove_intermediate_outputs(output_root: Path) -> int:
    """Keep each source-stage raw block plus its final PNG and metadata."""
    removed = 0
    for path in output_root.rglob("*.idx.jpn.bin"):
        path.unlink()
        removed += 1

    for path in output_root.rglob("*.pln.jpn.bin"):
        stem = path.name.removesuffix(".pln.jpn.bin")
        metadata_path = path.with_name(f"{stem}.meta.json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata["compression"] != "none":
            path.unlink()
            removed += 1

    for path in output_root.rglob("*.cmp.jpn.bin"):
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
        default=Path("c:/work_han/workspace1"),
        help=("workspace containing jpn-pc98 and image-pc98 (default: c:/work_han/workspace)"),
    )
    parser.add_argument(
        "--all-artifacts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=("also keep compressed, planar, and indexed artifacts (default: no-all-artifacts)"),
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    input_root = workspace / "jpn-pc98"
    output_root = workspace / "image-pc98"
    npk016_archives = sorted(
        path
        for path in input_root.rglob("*")
        if path.is_file() and (path.suffix.lower() == ".npk" or path.name.upper() == "GRAPH.DAT")
    )
    kao_archives = sorted(path for path in input_root.rglob("*") if path.is_file() and path.name.upper() == "KAO.LZW")
    lzdata_archives = sorted(path for path in input_root.rglob("*") if path.is_file() and path.name.upper() == "LZDATA.LZW")
    put_archives = sorted(path for path in input_root.rglob("*") if path.is_file() and path.name.upper() == "PUT.DAT")
    name_bmd_archives = sorted(path for path in input_root.rglob("*") if path.is_file() and path.name.upper() == "NAME.BMD")
    btgrp_archives = sorted(path for path in input_root.rglob("*") if path.is_file() and path.name.upper() == "BTGRP.DAT")
    bgobj_archives = sorted(path for path in input_root.rglob("*") if path.is_file() and path.name.upper() == "BGOBJ.DAT")
    if (
        not npk016_archives
        and not kao_archives
        and not lzdata_archives
        and not put_archives
        and not name_bmd_archives
        and not btgrp_archives
        and not bgobj_archives
    ):
        raise SystemExit(f"no supported image files found below {input_root}")

    total = 0
    failures: list[str] = []
    for source in npk016_archives:
        try:
            total += extract_archive(source, input_root, output_root)
        except NpkError as error:
            failures.append(f"{source.relative_to(input_root)}: {error}")
    for source in kao_archives:
        try:
            total += extract_kao(source, input_root, output_root)
        except Ls11Error as error:
            failures.append(f"{source.relative_to(input_root)}: {error}")
    for source in lzdata_archives:
        try:
            total += extract_lzdata(source, input_root, output_root)
        except Ls11Error as error:
            failures.append(f"{source.relative_to(input_root)}: {error}")
    for source in put_archives:
        try:
            total += extract_put(source, input_root, output_root)
        except ValueError as error:
            failures.append(f"{source.relative_to(input_root)}: {error}")
    for source in name_bmd_archives:
        try:
            total += extract_name_bmd(source, input_root, output_root)
        except ValueError as error:
            failures.append(f"{source.relative_to(input_root)}: {error}")
    for source in btgrp_archives:
        try:
            total += extract_btgrp(source, input_root, output_root)
        except NpkError as error:
            failures.append(f"{source.relative_to(input_root)}: {error}")
    for source in bgobj_archives:
        try:
            total += extract_bgobj(source, input_root, output_root)
        except NpkError as error:
            failures.append(f"{source.relative_to(input_root)}: {error}")

    if failures:
        for failure in failures:
            print(f"error: {failure}")
        return 1
    if not args.all_artifacts:
        removed = remove_intermediate_outputs(output_root)
        print(f"removed {removed} intermediate binary files")
    print(f"wrote {total} images below {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
