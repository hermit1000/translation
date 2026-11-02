"""Decode FQ3 GDATA.CHR's Huffman/LZ font data and write an LZ-only file."""

from __future__ import annotations

from .end_codec import compress as compress_lz


def word(data: bytes, at: int) -> int:
    return int.from_bytes(data[at:at + 2], "little")


def decode_huffman(source: bytes) -> bytes:
    if word(source, 0) != 0:
        raise ValueError("unsupported GDATA Huffman patch table")
    header = 2
    compressed_at = header + word(source, header)
    expected = word(source, header + 2)
    tree = header + 4
    output = bytearray()
    cursor = compressed_at
    bit_mask = 0
    bits = 0
    while len(output) < expected:
        node = 0
        while True:
            if bit_mask == 0:
                if cursor >= len(source):
                    raise ValueError("GDATA Huffman stream ended early")
                bits = source[cursor]
                cursor += 1
                bit_mask = 0x80
            branch = bool(bits & bit_mask)
            bit_mask >>= 1
            value = word(source, tree + node + 2 * branch)
            if value >> 8 == 0xFF:
                output.append(value & 0xFF)
                break
            node = value * 4
    if cursor != len(source):
        raise ValueError("trailing GDATA Huffman bytes")
    return bytes(output)


def decode_lz(source: bytes) -> bytes:
    if len(source) < 4 or source[1] != 0:
        raise ValueError("unexpected GDATA LZ header")
    marker = source[0]
    expected = word(source, 2)
    output = bytearray()
    cursor = 4
    while len(output) < expected:
        if cursor >= len(source):
            raise ValueError("GDATA LZ stream ended early")
        value = source[cursor]
        cursor += 1
        if value != marker:
            output.append(value)
            continue
        token = word(source, cursor)
        cursor += 2
        if token == 1:
            output.append(marker)
            continue
        distance = token & 0xFFF or 0x1000
        length = (token >> 12) + 4
        if distance > len(output):
            raise ValueError("invalid GDATA LZ distance")
        for _ in range(length):
            output.append(output[-distance])
    if cursor != len(source):
        raise ValueError("trailing GDATA LZ bytes")
    return bytes(output)


def decompress(source: bytes) -> bytes:
    mode = word(source, 0)
    if mode == 9:
        stage = decode_huffman(source[2:])
    elif mode == 3:
        stage = source[2:]
    else:
        raise ValueError(f"unsupported GDATA compression mode {mode}")
    return decode_lz(stage)


def compress(source: bytes) -> bytes:
    # Mode 3 runs the same LZ decoder without GDATA's Huffman stage.
    template = b"\x03\x00\x7B\x00" + len(source).to_bytes(2, "little")
    result = compress_lz(source, template)
    if len(result) > 0x9400:
        raise ValueError(f"GDATA exceeds the game's 0x9400-byte read buffer: {len(result)}")
    if decompress(result) != source:
        raise ValueError("GDATA LZ round-trip failed")
    return result
