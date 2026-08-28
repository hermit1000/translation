#!/usr/bin/env python3
"""Decode Winning Post (PC-98) image resources into image-pc98."""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from module.pc98_image.planar import decode_interleaved_planar

SIGNATURE = b"NPK016"
HEADER_SIZE = 0x0E
RING_SIZE = 0x640
RING_ROW_STRIDE = 0x140
PALETTE_8 = [
    (0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255),
    (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255),
]
PALETTE_16 = PALETTE_8 + [
    (128, 128, 128), (128, 128, 255), (255, 128, 128), (255, 128, 255),
    (128, 255, 128), (128, 255, 255), (255, 255, 128), (255, 255, 255),
]

OPEN_PU_MASK_OFFSET = 0x5045
OPEN_PU_MASK_WIDTH = 368
OPEN_PU_MASK_HEIGHT = 200
OPEN_PU_MASK_SIZE = OPEN_PU_MASK_WIDTH * OPEN_PU_MASK_HEIGHT // 8


class DecodeError(ValueError):
    pass


class BitReader:
    def __init__(self, data: bytes):
        self.data = data
        self.byte_pos = self.value = self.bits_left = 0

    def read_bit(self) -> int:
        if not self.bits_left:
            if self.byte_pos >= len(self.data):
                raise DecodeError("LW10 stream ended early")
            self.value = self.data[self.byte_pos]
            self.byte_pos += 1
            self.bits_left = 8
        bit = (self.value >> 7) & 1
        self.value = (self.value << 1) & 0xFF
        self.bits_left -= 1
        return bit

    def read_code(self) -> int:
        prefix = width = 0
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


@dataclass(frozen=True)
class Entry:
    offset: int
    size: int
    width: int
    height: int
    block: bytes


def parse_entries(data: bytes) -> list[Entry]:
    entries = []
    offset = 0
    while (offset := data.find(SIGNATURE, offset)) >= 0:
        if offset + HEADER_SIZE > len(data):
            break
        planes, width, height, size = struct.unpack_from("<HHHH", data, offset + 6)
        if planes != 4 or not width or not height or size < HEADER_SIZE or offset + size > len(data):
            offset += 1
            continue
        entries.append(Entry(offset, size, width, height, data[offset : offset + size]))
        offset += size
    return entries


def decompress(payload: bytes, width: int, height: int) -> bytes:
    words_per_row = (width + 3) // 4
    ring = bytearray(RING_SIZE)
    source_pos = ring_row = control = control_bits = 0
    packed = bytearray()

    def read_byte() -> int:
        nonlocal source_pos
        if source_pos >= len(payload):
            raise DecodeError("NPK016 stream ended early")
        value = payload[source_pos]
        source_pos += 1
        return value

    for _ in range(height):
        write_pos = ring_row
        produced = 0
        while produced < words_per_row:
            if not control_bits:
                control, control_bits = read_byte(), 8
            is_backref = control & 1
            control >>= 1
            control_bits -= 1
            if not is_backref:
                count = 1
                for value in (read_byte(), read_byte()):
                    ring[write_pos % RING_SIZE] = value
                    write_pos += 1
                    packed.append(value)
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
                    packed.append(value)
            produced += count
            if produced > words_per_row:
                raise DecodeError("NPK016 command crosses a row boundary")
        ring_row = (ring_row + RING_ROW_STRIDE) % RING_SIZE
    return bytes(packed)


def packed_to_indices(packed: bytes, width: int, height: int) -> bytes:
    words_per_row = (width + 3) // 4
    if len(packed) != words_per_row * height * 2:
        raise DecodeError("invalid NPK016 decompressed size")
    indices = bytearray()
    source_pos = 0
    for _ in range(height):
        row = bytearray()
        for _ in range(words_per_row):
            gi, br = packed[source_pos : source_pos + 2]
            source_pos += 2
            masks = (br & 0x0F, br >> 4, gi & 0x0F, gi >> 4)
            for bit in (3, 2, 1, 0):
                row.append(sum(((mask >> bit) & 1) << plane for plane, mask in enumerate(masks)))
        indices.extend(row[:width])
    return bytes(indices)


def save_png(path: Path, indices: bytes, width: int, height: int, palette: list[tuple[int, int, int]]) -> None:
    rgb = bytes(component for index in indices for component in palette[index])
    Image.frombytes("RGB", (width, height), rgb).save(path)


def write_meta(path: Path, metadata: dict[str, object]) -> None:
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def base_meta(source: Path, offset: int, size: int, compression: str, width: int, height: int) -> dict[str, object]:
    return {
        "source": source.as_posix(), "offset": f"0x{offset:06X}", "original_size": size,
        "encoded_size": None, "stored_size": None, "padding_byte": None,
        "compression": compression, "width": width, "height": height,
    }


def extract_npk(source: Path, input_root: Path, output_root: Path) -> int:
    entries = parse_entries(source.read_bytes())
    if not entries:
        return 0
    relative = source.relative_to(input_root)
    destination = output_root / relative
    destination.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        stem = f"{entry.offset:06x}"
        indices = packed_to_indices(decompress(entry.block[HEADER_SIZE:], entry.width, entry.height), entry.width, entry.height)
        palette = PALETTE_16
        (destination / f"{stem}.cmp.jpn.bin").write_bytes(entry.block)
        (destination / f"{stem}.idx.jpn.bin").write_bytes(indices)
        save_png(destination / f"{stem}.jpn.png", indices, entry.width, entry.height, palette)
        metadata = base_meta(relative, entry.offset, entry.size, "npk016-lz", entry.width, entry.height)
        metadata.update({
            "planes": 4, "plane_order": "BRGI", "planar_layout": None,
            "packed_layout": "four-pixel-bitplane-words", "bit_order": "msb-first",
            "stride": (entry.width + 3) // 4 * 2, "header_size": HEADER_SIZE,
            "palette": "PC-98 default 16-color (display palette is not stored in NPK016)",
        })
        write_meta(destination / f"{stem}.meta.json", metadata)
    extra_count = 0
    if source.name.upper() == "OPEN_PU.DAT":
        mask_end = OPEN_PU_MASK_OFFSET + OPEN_PU_MASK_SIZE
        if mask_end > len(source.read_bytes()):
            raise DecodeError("OPEN_PU.DAT is too short for its 007435 mask")
        mask = source.read_bytes()[OPEN_PU_MASK_OFFSET:mask_end]
        indices = bytes(
            (byte >> bit) & 1
            for byte in mask
            for bit in range(7, -1, -1)
        )
        stem = f"{OPEN_PU_MASK_OFFSET:06x}"
        (destination / f"{stem}.pln.jpn.bin").write_bytes(mask)
        (destination / f"{stem}.idx.jpn.bin").write_bytes(indices)
        save_png(
            destination / f"{stem}.jpn.png",
            indices,
            OPEN_PU_MASK_WIDTH,
            OPEN_PU_MASK_HEIGHT,
            [PALETTE_8[0], PALETTE_8[7]],
        )
        metadata = base_meta(
            relative,
            OPEN_PU_MASK_OFFSET,
            OPEN_PU_MASK_SIZE,
            "none",
            OPEN_PU_MASK_WIDTH,
            OPEN_PU_MASK_HEIGHT,
        )
        metadata.update({
            "planes": 1,
            "plane_order": "mask",
            "planar_layout": "row-major",
            "bit_order": "msb-first",
            "stride": OPEN_PU_MASK_WIDTH // 8,
            "palette": "monochrome preview; 0=masked/drawn, 1=preserved",
            "target_image_offset": "0x007435",
        })
        write_meta(destination / f"{stem}.meta.json", metadata)
        extra_count = 1
    print(f"{relative}: {len(entries)} NPK016 images, {extra_count} raw masks")
    return len(entries) + extra_count


def extract_kao(source: Path, input_root: Path, output_root: Path) -> int:
    width, height, planes = 64, 80, 3
    record_size = width * height * planes // 8
    data = source.read_bytes()
    if source.name.upper() != "KAO.DAT" or len(data) % record_size:
        return 0
    relative = source.relative_to(input_root)
    destination = output_root / relative
    destination.mkdir(parents=True, exist_ok=True)
    for index, offset in enumerate(range(0, len(data), record_size)):
        stem = f"{offset:06x}"
        planar = data[offset : offset + record_size]
        indices = decode_interleaved_planar(planar, width, height, planes)
        (destination / f"{stem}.pln.jpn.bin").write_bytes(planar)
        (destination / f"{stem}.idx.jpn.bin").write_bytes(indices)
        save_png(destination / f"{stem}.jpn.png", indices, width, height, PALETTE_8)
        metadata = base_meta(relative, offset, record_size, "none", width, height)
        metadata.update({
            "planes": planes, "plane_order": "BRG", "planar_layout": "interleaved",
            "bit_order": "msb-first", "stride": width // 8 * planes,
            "palette": "PC-98 digital 8-color", "record_index": index,
        })
        write_meta(destination / f"{stem}.meta.json", metadata)
    count = len(data) // record_size
    print(f"{relative}: {count} portraits")
    return count


LW10_DIMENSIONS = {
    "JKB.LZW": (640, 400),
    "JKS.LZW": (200, 200),
    "RACEUMAB.LZW": (640, 384),
    "RACEUMAS.LZW": (640, 96),
}


def decompress_lw10(payload: bytes, table: bytes, output_size: int) -> bytes:
    reader = BitReader(payload)
    output = bytearray()
    while len(output) < output_size:
        code = reader.read_code()
        if code < 0x100:
            output.append(table[code])
            continue
        distance = code - 0x100
        length = reader.read_code() + 3
        if not distance or distance > len(output):
            raise DecodeError(f"invalid LW10 distance {distance} at output {len(output)}")
        for _ in range(length):
            output.append(output[-distance])
            if len(output) == output_size:
                break
    return bytes(output)


def extract_lw10(source: Path, input_root: Path, output_root: Path) -> int:
    dimensions = LW10_DIMENSIONS.get(source.name.upper())
    data = source.read_bytes()
    if dimensions is None or data[:4] != b"LW10" or len(data) < 0x130:
        return 0
    relative = source.relative_to(input_root)
    destination = output_root / relative
    destination.mkdir(parents=True, exist_ok=True)
    table = data[0x10:0x110]
    count = 0
    for record_index, descriptor_offset in enumerate(range(0x110, len(data), 0x20)):
        descriptor = data[descriptor_offset : descriptor_offset + 0x20]
        if len(descriptor) < 0x20 or not descriptor[0]:
            break
        compressed_size = int.from_bytes(descriptor[0x12:0x14], "big")
        output_size = int.from_bytes(descriptor[0x16:0x18], "big")
        data_offset = int.from_bytes(descriptor[0x1A:0x1C], "big")
        if not compressed_size or data_offset + compressed_size > len(data):
            raise DecodeError(f"invalid LW10 descriptor in {relative} at 0x{descriptor_offset:X}")
        width, height = dimensions
        if output_size != width * height // 8:
            raise DecodeError(f"unexpected LW10 output size in {relative}: {output_size}")
        compressed = data[data_offset : data_offset + compressed_size]
        planar = decompress_lw10(compressed, table, output_size)
        indices = decode_interleaved_planar(planar, width, height, 1)
        stem = f"{data_offset:06x}"
        (destination / f"{stem}.cmp.jpn.bin").write_bytes(compressed)
        (destination / f"{stem}.pln.jpn.bin").write_bytes(planar)
        (destination / f"{stem}.idx.jpn.bin").write_bytes(indices)
        save_png(destination / f"{stem}.jpn.png", indices, width, height, [PALETTE_8[0], PALETTE_8[7]])
        metadata = base_meta(relative, data_offset, compressed_size, "lw10", width, height)
        metadata.update({
            "decoded_size": output_size, "planes": 1, "plane_order": "mask",
            "planar_layout": "row-major", "bit_order": "msb-first", "stride": width // 8,
            "palette": "monochrome preview; draw color is selected by the game", "record_index": record_index,
            "record_name": descriptor[:0x12].split(b"\0", 1)[0].decode("ascii"),
            "descriptor_offset": f"0x{descriptor_offset:06X}",
        })
        write_meta(destination / f"{stem}.meta.json", metadata)
        count += 1
    print(f"{relative}: {count} LW10 images")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Decode Winning Post PC-98 graphics.")
    parser.add_argument("--workspace", type=Path, default=Path("c:/work_han/workspace3"))
    args = parser.parse_args()
    input_root = args.workspace.resolve() / "jpn-pc98"
    output_root = args.workspace.resolve() / "image-pc98"
    if not input_root.is_dir():
        raise SystemExit(f"input directory not found: {input_root}")
    total = 0
    for source in sorted(path for path in input_root.rglob("*") if path.is_file()):
        total += extract_npk(source, input_root, output_root)
        total += extract_kao(source, input_root, output_root)
        total += extract_lw10(source, input_root, output_root)
    print(f"wrote {total} images below {output_root}")


if __name__ == "__main__":
    main()
