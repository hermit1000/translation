#!/usr/bin/env python3
"""Encode a Winning Post PC-98 PNG as an NPK016 replacement block."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from PIL import Image

from decode_graphics import (
    HEADER_SIZE,
    PALETTE_16,
    RING_ROW_STRIDE,
    RING_SIZE,
    SIGNATURE,
    decompress,
    packed_to_indices,
)

DEFAULT_INPUT = Path(
    "c:/work_han/workspace3/binary_inputs-pc98/EXTNPK.NPK/00af2b.kor.png"
)
DEFAULT_OUTPUT = Path(
    "c:/work_han/workspace3/binary_inputs-pc98/EXTNPK.NPK/00af2b.cmp.kor.bin"
)
DEFAULT_TEMPLATE = Path(
    "c:/work_han/workspace3/image-pc98/EXTNPK.NPK/00af2b.cmp.jpn.bin"
)


def image_to_indices(image: Image.Image) -> bytes:
    rgb = image.convert("RGB")
    palette_map = {color: index for index, color in enumerate(PALETTE_16)}
    indices = bytearray()
    for color in rgb.getdata():
        index = palette_map.get(color)
        if index is None:
            index = min(
                range(len(PALETTE_16)),
                key=lambda candidate: sum(
                    (color[channel] - PALETTE_16[candidate][channel]) ** 2
                    for channel in range(3)
                ),
            )
        indices.append(index)
    return bytes(indices)


def indices_to_packed(indices: bytes, width: int, height: int) -> bytes:
    packed = bytearray()
    for y in range(height):
        row = indices[y * width : (y + 1) * width]
        for x in range(0, width, 4):
            pixels = row[x : x + 4] + bytes(max(0, x + 4 - width))
            masks = [0, 0, 0, 0]
            for pixel_number, index in enumerate(pixels):
                bit = 3 - pixel_number
                for plane in range(4):
                    masks[plane] |= ((index >> plane) & 1) << bit
            packed.extend((masks[2] | masks[3] << 4, masks[0] | masks[1] << 4))
    return bytes(packed)


def matching_words(
    target: bytes,
    start: int,
    remaining: int,
    ring: bytearray,
    valid: bytearray,
    write_pos: int,
    distance: int,
) -> int:
    """Return the decoder-exact match length, including overlapping back-references."""
    written: dict[int, int] = {}
    read_pos = (write_pos - distance) % RING_SIZE
    # The PC-98 decoder performs a forward REP MOVSW after wrapping the source
    # address only once.  It does not wrap again if that copy crosses the end
    # of the 0x640-byte ring.  Such commands appear valid to a modulo-based
    # verifier but read unrelated memory in the game and produce horizontal
    # streaks.  Original streams never emit a crossing reference.
    remaining = min(remaining, (RING_SIZE - read_pos) // 2)
    byte_count = 0
    for offset in range(remaining * 2):
        source_address = read_pos + offset
        if source_address in written:
            value = written[source_address]
        else:
            # The game's 0x640-byte work ring is not cleared before decoding.
            # Referencing a byte that this stream has not written yet copies
            # stale screen/work data.  A zero-initialized verifier hides this
            # error and produces the characteristic residual-image streaks.
            if not valid[source_address]:
                break
            value = ring[source_address]
        if value != target[start + offset]:
            break
        written[(write_pos + offset) % RING_SIZE] = value
        byte_count += 1
    return byte_count // 2


def compress(packed: bytes, width: int, height: int) -> bytes:
    words_per_row = (width + 3) // 4
    expected_size = words_per_row * height * 2
    if len(packed) != expected_size:
        raise ValueError(f"expected {expected_size} packed bytes, got {len(packed)}")

    ring = bytearray(RING_SIZE)
    valid = bytearray(RING_SIZE)
    ring_row = source_pos = 0
    tokens: list[tuple[bool, bytes]] = []

    for _ in range(height):
        write_pos = ring_row
        produced = 0
        while produced < words_per_row:
            remaining = min(32, words_per_row - produced)
            best_count = best_command = 0
            for vertical, unit in ((False, 2), (True, RING_ROW_STRIDE)):
                for selector in range(1, 5):
                    count = matching_words(
                        packed,
                        source_pos,
                        remaining,
                        ring,
                        valid,
                        write_pos,
                        selector * unit,
                    )
                    if count > best_count:
                        best_count = count
                        best_command = (
                            (0x80 if vertical else 0)
                            | ((selector - 1) << 5)
                            | (count - 1)
                        )

            count = best_count or 1
            byte_count = count * 2
            data = packed[source_pos : source_pos + byte_count]
            if best_count:
                tokens.append((True, bytes((best_command,))))
            else:
                tokens.append((False, data))
            for value in data:
                ring[write_pos % RING_SIZE] = value
                valid[write_pos % RING_SIZE] = 1
                write_pos += 1
            source_pos += byte_count
            produced += count
        ring_row = (ring_row + RING_ROW_STRIDE) % RING_SIZE

    payload = bytearray()
    for group_start in range(0, len(tokens), 8):
        group = tokens[group_start : group_start + 8]
        control = sum(1 << bit for bit, (is_backref, _) in enumerate(group) if is_backref)
        payload.append(control)
        for _, data in group:
            payload.extend(data)
    return bytes(payload)


def encode(image_path: Path, template_path: Path) -> tuple[bytes, int]:
    template = template_path.read_bytes()
    if len(template) < HEADER_SIZE or template[:6] != SIGNATURE:
        raise ValueError(f"not an NPK016 template: {template_path}")
    planes, width, height, stored_size = struct.unpack_from("<HHHH", template, 6)
    if planes != 4 or stored_size != len(template):
        raise ValueError("template header or stored size is invalid")

    image = Image.open(image_path)
    if image.size != (width, height):
        raise ValueError(f"expected {width}x{height}, got {image.width}x{image.height}")
    indices = image_to_indices(image)
    payload = compress(indices_to_packed(indices, width, height), width, height)
    encoded_size = HEADER_SIZE + len(payload)
    if encoded_size > stored_size:
        raise ValueError(f"encoded block is {encoded_size} bytes; slot is {stored_size} bytes")

    block = SIGNATURE + struct.pack("<HHHH", planes, width, height, stored_size) + payload
    block += bytes(stored_size - len(block))
    decoded = packed_to_indices(decompress(block[HEADER_SIZE:], width, height), width, height)
    if decoded != indices:
        raise AssertionError("NPK016 round-trip verification failed")
    return block, encoded_size


def main() -> None:
    parser = argparse.ArgumentParser(description="Encode 00af2b.kor.png as an NPK016 block.")
    parser.add_argument("input", type=Path, nargs="?", default=DEFAULT_INPUT)
    parser.add_argument("output", type=Path, nargs="?", default=DEFAULT_OUTPUT)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    args = parser.parse_args()

    block, encoded_size = encode(args.input, args.template)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(block)
    print(
        f"{args.input} -> {args.output} "
        f"(encoded={encoded_size}, stored={len(block)}, padding={len(block) - encoded_size})"
    )


if __name__ == "__main__":
    main()
