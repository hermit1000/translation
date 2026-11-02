"""FQ3 END.BIN LZ codec (the six-byte PC-98 overlay format)."""

from __future__ import annotations

from collections import defaultdict

HEADER_SIZE = 6
LZ_MARKERS = (0x7B, 0x9A)
RLE_MARKERS = (0x79, 0xF2)


def decompress_rle(source: bytes) -> bytes:
    """Decode the second stage used by END.BIN (MAIN.EXE sub_27F68)."""
    if len(source) < 4 or source[0] not in RLE_MARKERS or source[1] != source[0]:
        raise ValueError("unexpected END.BIN RLE header")
    marker = source[0]
    expected = int.from_bytes(source[2:4], "little")
    output = bytearray()
    cursor = 4
    while len(output) < expected:
        if cursor >= len(source):
            raise ValueError("END.BIN RLE stream ended early")
        value = source[cursor]
        cursor += 1
        if value == marker:
            if cursor + 2 > len(source):
                raise ValueError("truncated END.BIN RLE token")
            value, count = source[cursor:cursor + 2]
            cursor += 2
            if count == 0:
                count = 256
            output.extend(bytes((value,)) * count)
        else:
            output.append(value)
        if len(output) > expected:
            raise ValueError("END.BIN RLE output overflow")
    if cursor != len(source):
        raise ValueError("trailing bytes after END.BIN RLE stream")
    return bytes(output)


def patch_rle_literals(original: bytes, patched: bytes) -> bytes:
    """Patch first-stage literals while keeping the RLE stream valid."""
    if len(original) != len(patched) or original[:4] != patched[:4]:
        raise ValueError("RLE source length or header changed")
    if original[0] not in RLE_MARKERS or original[1] != original[0]:
        raise ValueError("unexpected END.BIN RLE header")
    marker = original[0]
    output = bytearray(original[:4])
    cursor = 4
    while cursor < len(original):
        if original[cursor] == marker:
            token = original[cursor:cursor + 3]
            replacement = patched[cursor:cursor + 3]
            if len(token) != 3:
                raise ValueError("truncated original RLE token")
            if token[2] == 1 and replacement[1:] == token[1:]:
                # An escaped single byte may be replaced by another glyph
                # byte; its three-byte representation is no longer needed.
                value = replacement[0]
                output.extend((marker, marker, 1) if value == marker else (value,))
            elif replacement == token:
                output.extend(token)
            else:
                raise ValueError(f"translation overlaps RLE run at {cursor + HEADER_SIZE:05X}")
            cursor += 3
        else:
            value = patched[cursor]
            output.extend((marker, marker, 1) if value == marker else (value,))
            cursor += 1
    return bytes(output)


def decompress(source: bytes) -> bytes:
    if len(source) < HEADER_SIZE or source[2] not in LZ_MARKERS or source[3] != 0:
        raise ValueError("END.BIN has an unexpected compression header")
    marker = source[2]
    expected = int.from_bytes(source[4:6], "little")
    output = bytearray()
    cursor = HEADER_SIZE
    while len(output) < expected:
        if cursor >= len(source):
            raise ValueError("END.BIN compression stream ended early")
        value = source[cursor]
        cursor += 1
        if value != marker:
            output.append(value)
            continue
        if cursor + 2 > len(source):
            raise ValueError("truncated END.BIN reference")
        token = int.from_bytes(source[cursor:cursor + 2], "little")
        cursor += 2
        if token == 1:
            output.append(marker)
            continue
        distance = token & 0xFFF or 0x1000
        length = (token >> 12) + 4
        if distance > len(output) or len(output) + length > expected:
            raise ValueError("invalid END.BIN reference")
        for _ in range(length):
            output.append(output[-distance])
    if cursor != len(source):
        raise ValueError("trailing bytes after END.BIN stream")
    return bytes(output)


def compress(decoded: bytes, template: bytes) -> bytes:
    if len(decoded) > 0xFFFF:
        raise ValueError("END.BIN decoded image exceeds 16-bit size")
    if len(template) < HEADER_SIZE or template[2] not in LZ_MARKERS or template[3] != 0:
        raise ValueError("END.BIN has an unexpected compression header")
    marker = template[2]
    positions: dict[bytes, list[int]] = defaultdict(list)
    body = bytearray()
    cursor = 0

    def remember(at: int) -> None:
        if at + 4 <= len(decoded):
            positions[decoded[at:at + 4]].append(at)

    while cursor < len(decoded):
        best_length = best_distance = 0
        if cursor + 4 <= len(decoded):
            for previous in reversed(positions.get(decoded[cursor:cursor + 4], ())):
                distance = cursor - previous
                if distance > 0x1000:
                    break
                length = 4
                maximum = min(19, len(decoded) - cursor)
                while length < maximum and decoded[cursor + length] == decoded[cursor + length - distance]:
                    length += 1
                if distance == 1 and length == 4:
                    continue
                if length > best_length:
                    best_length, best_distance = length, distance
                    if length == maximum:
                        break
        if best_length:
            field = best_distance if best_distance != 0x1000 else 0
            body.extend((marker,))
            body.extend((((best_length - 4) << 12) | field).to_bytes(2, "little"))
            for at in range(cursor, cursor + best_length):
                remember(at)
            cursor += best_length
        else:
            value = decoded[cursor]
            body.extend((marker, 1, 0) if value == marker else (value,))
            remember(cursor)
            cursor += 1
    return template[:4] + len(decoded).to_bytes(2, "little") + body
