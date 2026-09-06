"""Apply non-overlapping ADV replacements using inclusive source offsets."""


def apply_replacements(source: bytes, replacements: list[tuple[int, int, bytes]]) -> bytes:
    ordered = sorted(replacements, key=lambda item: item[0])
    parts = []
    cursor = 0
    for start, end, payload in ordered:
        if not 0 <= start <= end < len(source):
            raise ValueError(f"invalid translation range: {start}-{end}")
        if start < cursor:
            raise ValueError(f"translation ranges overlap at {start:05X}")
        parts.extend((source[cursor:start], payload))
        cursor = end + 1
    parts.append(source[cursor:])
    return b"".join(parts)
