"""Conservative ASCII recognition shared by DOB2 and Marine Philt.

This is a lexical heuristic, not a complete ADV command grammar.
"""

import re
from typing import Any
from .tokens import make_token, verify_tokens

def find_ascii_spans(data: bytes) -> dict[int, int]:
    """Return conservative, clearly English byte spans as start -> end."""
    spans: dict[int, int] = {}
    # 0x21 is ADV98's non-printing ASCII-output marker in DOB2.  Excluding it
    # keeps strings such as ``!Please ...`` aligned with the actual screen,
    # where the leading exclamation mark is not drawn.
    for match in re.finditer(rb"[\x20\x22-\x7e]{2,}", data):
        start, end = match.span()
        raw = match.group()
        stripped = raw.lstrip()
        # Quoted graphics commands and ``se "..."`` audio commands are
        # ADV98 operands, not screen text.  Leave them to the base lexer.
        if stripped.startswith(b'"') or stripped.lower().startswith(b'se "'):
            continue
        letters = bytes(value for value in raw if 0x41 <= value <= 0x5A or 0x61 <= value <= 0x7A)
        if len(letters) < 2:
            continue
        has_space = b" " in raw
        uppercase_label = letters == letters.upper()
        nul_terminated = end < len(data) and data[end] == 0
        a5_delimited = (
            start > 0
            and end < len(data)
            and data[start - 1] == 0xA5
            and data[end] == 0xA5
        )
        # Mixed-case text is accepted only when spacing or a NUL terminator
        # makes it unmistakably ASCII.  This avoids converting ordinary DOB2
        # compressed hiragana which happens to occupy printable ASCII bytes.
        if has_space or nul_terminated or (uppercase_label and a5_delimited):
            spans[start] = end
    return spans


def resolve_ascii_and_gaiji(data: bytes, base: list[dict[str, Any]]) -> list[dict[str, Any]]:
    token_starts = {token["offset"] for token in base}
    token_ends = {token["offset"] + token["size"] for token in base}
    ascii_spans: dict[int, int] = {}
    for raw_start, raw_end in find_ascii_spans(data).items():
        # A printable SJIS trail byte can attach itself to the front of an
        # English regex match.  Trim at most that one byte to a token boundary.
        starts = [value for value in (raw_start, raw_start + 1) if value in token_starts]
        ends = [value for value in (raw_end, raw_end - 1) if value in token_ends]
        if starts and ends and min(starts) < max(ends):
            ascii_spans[min(starts)] = max(ends)
    result: list[dict[str, Any]] = []
    index = 0

    while index < len(base):
        token = base[index]
        start = token["offset"]
        ascii_end = ascii_spans.get(start)
        if ascii_end is not None and token.get("syntax") != "ascii-output-nul":
            result.append(
                make_token(
                    start,
                    ascii_end - start,
                    data[start:ascii_end],
                    "text",
                    data[start:ascii_end].decode("ascii"),
                    encoding="ascii",
                    display_text=start > 0 and data[start - 1] == 0x21,
                )
            )
            while index < len(base) and base[index]["offset"] < ascii_end:
                index += 1
            continue

        raw = token["bytes"]
        if token["type"] == "text" and len(raw) == 2 and "\ufffd" in str(token["value"]):
            result.append(
                make_token(
                    start,
                    2,
                    bytes(raw),
                    "gaiji",
                    f"GAIJI_{raw[0]:02X}{raw[1]:02X}",
                )
            )
        else:
            result.append(token)
        index += 1

    verify_tokens(data, result)
    return result

