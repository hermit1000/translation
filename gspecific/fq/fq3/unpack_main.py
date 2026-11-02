"""Unpack the EXEPACK wrapper around FQ3 MAIN.EXE for static analysis.

The input is never modified. The generated EXE is an analysis artifact; its
runtime behavior must be checked in DOSBox-X before it is used for a patch.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


def word(data: bytes, at: int) -> int:
    return struct.unpack_from("<H", data, at)[0]


def unpack(source: bytes) -> tuple[bytes, bytes]:
    if source[:2] != b"MZ":
        raise ValueError("not an MZ executable")
    image_start = word(source, 8) * 16
    pack_start = image_start + word(source, 22) * 16
    fields = struct.unpack_from("<9H", source, pack_start)
    real_ip, real_cs, _, pack_size, real_sp, real_ss, dest_len, skip, signature = fields
    if b"RB" not in (struct.pack("<H", skip), struct.pack("<H", signature)):
        raise ValueError("not an EXEPACK executable")

    stream = source[image_start:pack_start][::-1]
    cursor = 0
    while stream[cursor] == 0xFF:
        cursor += 1
    output = bytearray()
    maximum = dest_len * 16
    while True:
        opcode = stream[cursor]
        count = (stream[cursor + 1] << 8) | stream[cursor + 2]
        cursor += 3
        if opcode & 0xFE == 0xB0:
            output.extend(bytes((stream[cursor],)) * count)
            cursor += 1
        elif opcode & 0xFE == 0xB2:
            output.extend(stream[cursor:cursor + count])
            cursor += count
        else:
            raise ValueError(f"unknown EXEPACK command {opcode:02X}")
        if len(output) > maximum:
            raise ValueError("unpacked image exceeds EXEPACK destination")
        if opcode & 1:
            break
    output.extend(stream[cursor:])
    image = bytes(output[::-1])

    marker = source.find(b"Packed file is corrupt", pack_start)
    if marker < 0:
        raise ValueError("EXEPACK relocation table marker not found")
    cursor = marker + len(b"Packed file is corrupt")
    relocations = bytearray()
    for group in range(16):
        count = word(source, cursor)
        cursor += 2
        for _ in range(count):
            relocations.extend(struct.pack("<HH", word(source, cursor), group * 0x1000))
            cursor += 2

    header_size = (28 + len(relocations) + 511) // 512 * 512
    total = header_size + len(image)
    header = bytearray(header_size)
    struct.pack_into("<14H", header, 0,
                     0x5A4D, total % 512, (total + 511) // 512,
                     len(relocations) // 4, header_size // 16,
                     word(source, 10), 0xFFFF, real_ss, real_sp,
                     0, real_ip, real_cs, 28, 0)
    header[28:28 + len(relocations)] = relocations
    return bytes(header) + image, image


def literal_byte_map(source: bytes, image_size: int) -> dict[int, int]:
    """Map unpacked image offsets to the packed file's literal byte offsets."""
    image_start = word(source, 8) * 16
    pack_start = image_start + word(source, 22) * 16
    stream = source[image_start:pack_start][::-1]
    cursor = 0
    while stream[cursor] == 0xFF:
        cursor += 1
    written = 0
    mapping: dict[int, int] = {}
    while True:
        opcode = stream[cursor]
        count = (stream[cursor + 1] << 8) | stream[cursor + 2]
        cursor += 3
        if opcode & 0xFE == 0xB0:
            cursor += 1
        elif opcode & 0xFE == 0xB2:
            for j in range(count):
                mapping[image_size - 1 - (written + j)] = pack_start - 1 - (cursor + j)
            cursor += count
        else:
            raise ValueError(f"unknown EXEPACK command {opcode:02X}")
        written += count
        if opcode & 1:
            break
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    executable, image = unpack(args.source.read_bytes())
    args.output.write_bytes(executable)
    print(f"unpacked image: {len(image)} bytes; EXE: {len(executable)} bytes")
    print(f"END.BIN offsets in image: {[hex(i) for i in range(len(image)) if image.startswith(b'END.BIN', i)]}")


if __name__ == "__main__":
    main()
