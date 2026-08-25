#!/usr/bin/env python3
"""Decrypt Ides ADV98 ``TC0``-wrapped MZ executables.

Python port of ValleyBell's GPL-2.0 ``adv98_dec.c`` from:
https://github.com/ValleyBell/ExtractorsDecoders
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


def read_u16(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def write_u16(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<H", data, offset, value)


def tc0_offset(data: bytes | bytearray) -> int:
    return read_u16(data, 0x08) * 0x10 + read_u16(data, 0x16) * 0x10 + read_u16(data, 0x14)


def has_tc0(data: bytes | bytearray, offset: int) -> bool:
    return offset + 0x14 <= len(data) and data[offset + 3 : offset + 6] == b"TC0"


def find_key_code(data: bytes | bytearray, start: int) -> int | None:
    for pos in range(start, len(data) - 7):
        if data[pos] == 0xBE and data[pos + 5] == 0x05:
            return pos
    return None


def decode_layer(data: bytearray) -> bytearray:
    header_size = read_u16(data, 0x08) * 0x10
    wrapper = tc0_offset(data)
    key_initial = read_u16(data, wrapper + 0x06)
    decode_length = read_u16(data, wrapper + 0x08)
    key_code = find_key_code(data, wrapper)
    if key_code is None:
        key_mult, key_add = 0x2711, 0x3619
    else:
        key_mult = read_u16(data, key_code + 0x01)
        key_add = read_u16(data, key_code + 0x06)

    if header_size + decode_length > len(data):
        raise ValueError("TC0 decode length extends beyond the input file")

    key = key_initial
    for pos in range(decode_length):
        key = (key * key_mult + key_add) & 0xFFFF
        data[header_size + pos] ^= (key >> 6) & 0xFF

    new_length = header_size + decode_length
    data[0x14:0x18] = data[wrapper + 0x0C : wrapper + 0x10]
    data[0x10:0x12] = data[wrapper + 0x10 : wrapper + 0x12]
    data[0x0E:0x10] = data[wrapper + 0x12 : wrapper + 0x14]

    page_count = (new_length + 0x1FF) // 0x200
    last_page = new_length & 0x1FF
    if last_page == 0:
        last_page = 0x200
    write_u16(data, 0x02, last_page)
    write_u16(data, 0x04, page_count)

    print(
        f"decoded layer: bytes=0x{decode_length:04X}, "
        f"key=0x{key_initial:04X}/0x{key_mult:04X}/0x{key_add:04X}, "
        f"size=0x{len(data):X}->0x{new_length:X}"
    )
    return data[:new_length]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    data = bytearray(args.input.read_bytes())
    if data[:2] != b"MZ":
        raise ValueError("input is not an MZ executable")

    layers = 0
    while has_tc0(data, tc0_offset(data)):
        data = decode_layer(data)
        layers += 1
    if layers == 0:
        raise ValueError("TC0 signature not found")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"wrote {args.output} ({len(data)} bytes, {layers} layers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
