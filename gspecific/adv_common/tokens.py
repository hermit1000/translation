"""ADV token construction and complete source-range validation."""

from typing import Any

def is_sjis_lead(value: int) -> bool:
    return 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC


def is_sjis_trail(value: int) -> bool:
    return 0x40 <= value <= 0x7E or 0x80 <= value <= 0xFC


def decode_pair(first: int, second: int) -> str:
    return bytes((first, second)).decode("cp932", errors="replace")


def make_token(
    offset: int,
    size: int,
    raw: bytes,
    token_type: str,
    value: str | int,
    **extra: Any,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "offset": offset,
        "size": size,
        "bytes": list(raw),
        "type": token_type,
        "value": value,
    }
    result.update(extra)
    return result


def verify_tokens(data: bytes, tokens: list[dict[str, Any]]) -> None:
    offset = 0
    for token in tokens:
        raw = bytes(token["bytes"])
        if token["offset"] != offset or token["size"] != len(raw) or not raw:
            raise ValueError(f"invalid token range at {offset:05X}")
        if data[offset:offset + len(raw)] != raw:
            raise ValueError(f"token bytes mismatch at {offset:05X}")
        offset += len(raw)
    if offset != len(data):
        raise ValueError("decoded tokens do not cover the original MES bytes")
