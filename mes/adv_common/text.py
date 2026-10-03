"""ADV text and Korean font encoding shared by game adapters."""

import json
import pickle
from pathlib import Path

from .tokens import is_sjis_trail

FORBIDDEN_CONTROL_PAIRS = frozenset({0x8197, 0x8190, 0x816F, 0x8170})


def encode_adv98_text(text: str) -> bytes:
    """Encode original CP932 text using ADV98's compressed hiragana form."""
    output = bytearray()
    for character in text:
        encoded = character.encode("cp932")
        if len(encoded) == 1:
            value = encoded[0]
            if not 0x2D <= value <= 0x7F:
                raise ValueError(
                    f"single-byte character {character!r} becomes control byte {value:02X}"
                )
            output.append(value)
            continue
        if len(encoded) != 2:
            raise ValueError(f"unsupported CP932 length for {character!r}")
        word = encoded[0] << 8 | encoded[1]
        if word in FORBIDDEN_CONTROL_PAIRS:
            raise ValueError(f"{character!r} is an ADV98 control token")
        compressed = encoded[1] - 0x72
        if encoded[0] == 0x82 and 0x2D <= compressed <= 0x7F:
            output.append(compressed)
        else:
            output.extend(encoded)
    return bytes(output)


def parse_offset(value: str | int) -> int:
    if isinstance(value, int):
        return value
    return int(value, 16)


def load_font_codes(path: Path) -> dict[str, str]:
    if path.suffix.lower() == ".json":
        code_to_char = json.loads(path.read_text(encoding="utf-8"))
        codes: dict[str, str] = {}
        for code, character in code_to_char.items():
            codes.setdefault(character, code)
    else:
        # The project-supplied pickle contains module.font_table.FontTable.
        table = pickle.loads(path.read_bytes())
        codes = dict(table.char2code)
    if " " not in codes and "_" in codes:
        codes[" "] = codes["_"]
    return codes


def load_forced_dbcs_codes(path: Path) -> dict[str, str]:
    """Load a preferred two-byte font code for forced-character tokens."""
    if path.suffix.lower() == ".json":
        table = json.loads(path.read_text(encoding="utf-8"))
        forced: dict[str, str] = {}
        for code, character in table.items():
            if isinstance(code, str) and len(code) == 4 and isinstance(character, str):
                forced[character] = code
        return forced
    table = pickle.loads(path.read_bytes())
    return {
        character: code
        for character, code in table.char2code.items()
        if isinstance(code, str) and len(code) == 4
    }


def load_marine_remap(path: Path | None) -> dict[str, int]:
    """Load a Marine compressed-code remap table."""
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    remap: dict[str, int] = {}
    for entry in data.get("entries", []):
        character = entry.get("character")
        code = entry.get("code")
        if not isinstance(character, str) or len(character) != 1:
            raise ValueError(f"invalid Marine remap character: {character!r}")
        value = int(str(code), 16)
        if not 0x2D <= value <= 0x7F:
            raise ValueError(f"Marine remap code must be 2D..7F: {code}")
        remap[character] = value
    return remap


def encode_translation(
    text: str, codes: dict[str, str], *,
    allowed_nonstandard_codes: frozenset[int] = frozenset(),
    forbidden_control_pairs: frozenset[int] = FORBIDDEN_CONTROL_PAIRS,
    one_byte_codes: dict[str, int] | None = None,
) -> bytes:
    """Encode font glyphs, allowing only explicitly verified nonstandard pairs.

    MES control pairs are reserved by default. Plain-text DAT adapters can
    pass an empty forbidden_control_pairs set without weakening MES callers.
    """
    output = bytearray()
    for character in text:
        if one_byte_codes is not None and character in one_byte_codes:
            output.append(one_byte_codes[character])
            continue
        code = codes.get(character)
        if code is None:
            raise ValueError(f"character {character!r} is absent from the selected font table")
        raw = bytes.fromhex(code)
        if len(raw) != 2:
            raise ValueError(f"character {character!r} maps to unsupported code {code}")
        first, second = raw
        if not ((0x81 <= first <= 0x9F) or (0xE0 <= first <= 0xFC)):
            raise ValueError(f"character {character!r} maps to non-DBCS lead byte {code}")
        word = first << 8 | second
        if word in forbidden_control_pairs:
            raise ValueError(f"character {character!r} maps to an ADV98 control token {code}")
        if not is_sjis_trail(second) and word not in allowed_nonstandard_codes:
            raise ValueError(f"character {character!r} maps to non-DBCS trail byte {code}")
        output.extend(raw)
    return bytes(output)


def encode_tokenized_translation(
    text: str,
    codes: dict[str, str],
    *,
    forced_dbcs_codes: dict[str, str] | None = None,
    one_byte_codes: dict[str, int] | None = None,
) -> bytes:
    """Encode text with explicit fullwidth-space and forced-DBCS tokens.

    ``{ }`` emits CP932 fullwidth space ``81 40``.  ``{문자}`` forces the
    selected character through its two-byte font code.  The legacy ``_``
    fullwidth-space token is retained for compatibility.
    """
    forced_dbcs_codes = forced_dbcs_codes or {}
    output = bytearray()
    chunk: list[str] = []

    def flush() -> None:
        if chunk:
            output.extend(
                encode_translation("".join(chunk), codes, one_byte_codes=one_byte_codes)
            )
            chunk.clear()

    index = 0
    while index < len(text):
        character = text[index]
        if character == "_":
            flush()
            output.extend(b"\x81\x40")
            index += 1
            continue
        if character == "{" :
            closing = text.find("}", index + 1)
            if closing >= 0:
                token = text[index + 1 : closing]
                if token == " ":
                    flush()
                    output.extend(b"\x81\x40")
                    index = closing + 1
                    continue
                if len(token) == 1:
                    forced = forced_dbcs_codes.get(token)
                    if forced is None:
                        raise ValueError(f"character {token!r} has no forced 2-byte font code")
                    flush()
                    output.extend(bytes.fromhex(forced))
                    index = closing + 1
                    continue
        chunk.append(character)
        index += 1
    flush()
    return bytes(output)


