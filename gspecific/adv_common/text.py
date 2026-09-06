"""ADV text and Korean font encoding shared by game adapters."""

import json
import pickle
from pathlib import Path

FORBIDDEN_CONTROL_PAIRS = {0x8197, 0x8190, 0x816F, 0x8170}


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


def encode_translation(text: str, codes: dict[str, str]) -> bytes:
    output = bytearray()
    for character in text:
        code = codes.get(character)
        if code is None:
            raise ValueError(f"character {character!r} is absent from the selected font table")
        raw = bytes.fromhex(code)
        if len(raw) != 2:
            raise ValueError(f"character {character!r} maps to unsupported code {code}")
        first, second = raw
        if not ((0x81 <= first <= 0x9F) or (0xE0 <= first <= 0xFC)):
            raise ValueError(f"character {character!r} maps to non-DBCS lead byte {code}")
        output.extend(raw)
    return bytes(output)


