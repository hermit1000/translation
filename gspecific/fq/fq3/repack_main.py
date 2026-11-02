"""Re-encode FQ3's EXEPACK image without moving its wrapper or changing its size."""

from __future__ import annotations

from pathlib import Path

from .unpack_main import unpack, word


def encode_stream(image: bytes) -> bytes:
    data = image[::-1]
    length = len(data)
    size = 1 << (length + 1).bit_length()
    inf = 1 << 60
    literal_tree = [(inf, 0)] * (size * 2)
    repeat_tree = [(inf, 0)] * (size * 2)

    def update(tree: list[tuple[int, int]], at: int, value: tuple[int, int]) -> None:
        at += size
        tree[at] = value
        while at > 1:
            at >>= 1
            tree[at] = min(tree[at * 2], tree[at * 2 + 1])

    def minimum(tree: list[tuple[int, int]], start: int, end: int) -> tuple[int, int]:
        start += size
        end += size
        result = (inf, 0)
        while start < end:
            if start & 1:
                result = min(result, tree[start])
                start += 1
            if end & 1:
                end -= 1
                result = min(result, tree[end])
            start >>= 1
            end >>= 1
        return result

    cost = [0] * (length + 1)
    choice: list[tuple[str, int]] = [("raw", length)] * (length + 1)
    run_end = length
    update(literal_tree, length, (length, length))
    update(repeat_tree, length, (0, length))
    for at in range(length - 1, -1, -1):
        if at + 1 == length or data[at] != data[at + 1]:
            run_end = at + 1
        best = length - at
        action = ("raw", length)
        literal_value, literal_to = minimum(literal_tree, at + 1, min(length, at + 65535) + 1)
        if 3 - at + literal_value < best:
            best = 3 - at + literal_value
            action = ("literal", literal_to)
        if run_end - at >= 2:
            repeat_value, repeat_to = minimum(repeat_tree, at + 1, min(run_end, at + 65535) + 1)
            if 4 + repeat_value < best:
                best = 4 + repeat_value
                action = ("repeat", repeat_to)
        cost[at] = best
        choice[at] = action
        update(literal_tree, at, (at + best, at))
        update(repeat_tree, at, (best, at))

    commands: list[bytes] = []
    at = 0
    while at < length:
        kind, end = choice[at]
        if kind == "raw":
            break
        count = end - at
        if kind == "literal":
            commands.append(bytes((0xB2, count >> 8, count & 0xFF)) + data[at:end])
        else:
            commands.append(bytes((0xB0, count >> 8, count & 0xFF, data[at])))
        at = end
    if not commands:
        raise ValueError("no EXEPACK commands")
    last = bytearray(commands[-1])
    last[0] |= 1
    commands[-1] = bytes(last)
    return b"".join(commands) + data[at:]


def repack(source: bytes, image: bytes) -> bytes:
    image_start = word(source, 8) * 16
    pack_start = image_start + word(source, 22) * 16
    capacity = pack_start - image_start
    stream = encode_stream(image)
    if len(stream) > capacity:
        raise ValueError(f"EXEPACK stream needs {len(stream)} bytes; only {capacity} available")
    # The DOS EXEPACK stub scans at most 16 trailing FF bytes before reading
    # the first command. Split a literal command if compression leaves more.
    while capacity - len(stream) >= 16:
        cursor = 0
        while cursor < len(stream):
            opcode = stream[cursor]
            count = (stream[cursor + 1] << 8) | stream[cursor + 2]
            if opcode & 0xFE == 0xB2 and count >= 2:
                split = cursor + 4
                stream = (stream[:cursor] + bytes((0xB2, 0, 1))
                          + stream[cursor + 3:split]
                          + bytes((opcode, (count - 1) >> 8, (count - 1) & 0xFF))
                          + stream[split:])
                break
            cursor += 4 if opcode & 0xFE == 0xB0 else 3 + count
        else:
            raise ValueError("cannot limit EXEPACK padding to 15 bytes")
    packed = bytearray(source)
    packed[image_start:pack_start] = (b"\xFF" * (capacity - len(stream)) + stream)[::-1]
    _, check_image = unpack(bytes(packed))
    if check_image != image:
        raise ValueError("repacked image does not round-trip")
    return bytes(packed)


def main() -> None:
    source = Path(r"C:\work_han\workspace13\jpn-pc98\MAIN.EXE").read_bytes()
    _, image = unpack(source)
    result = repack(source, image)
    print(f"source={len(source)} repacked={len(result)} changed={sum(a != b for a,b in zip(source,result))}")


if __name__ == "__main__":
    main()
