"""Extract FQ3 END.BIN text from its decompressed image.

Run: python -m gspecific.fq.fq3.extract_end [workspace]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from module.font_table import FontTable

from .end_codec import HEADER_SIZE, decompress

DEFAULT_WORKSPACE = Path(__file__).resolve().parents[4] / "workspace13"
FONT_PATH = Path(__file__).resolve().parents[3] / "font_table" / "font_table-jpn.json"
# Addresses refer to the loaded, decompressed overlay (header occupies 0..5).
TEXT_RANGES = (
    (0x00FAE, 0x01014),  # status labels
    (0x017B7, 0x01DBC),  # map names
    (0x02D70, 0x0389C),  # ending narration and credits
    (0x048C6, 0x0490D),  # disk prompts
)
ENDING_STARTS = (
    0x02D70, 0x02DA8, 0x02E26, 0x02EA6, 0x02F1C, 0x02F98,
    0x03018, 0x03090, 0x03112, 0x0318E, 0x0320A, 0x032C4,
    0x0330A, 0x0337A, 0x033FE,
)


def extract_text(decoded: bytes, table: FontTable) -> dict[str, str]:
    result: dict[str, str] = {}
    for first, last in TEXT_RANGES:
        start = first - HEADER_SIZE
        stop = last - HEADER_SIZE + 1
        if start < 0 or stop > len(decoded):
            raise ValueError(f"text region {first:05X}-{last:05X} is out of range")
        cursor = start
        while cursor + 1 < stop:
            segment_start = cursor
            characters: list[str] = []
            while cursor + 1 < stop:
                code = decoded[cursor:cursor + 2].hex().upper()
                char = table.get_char(code)
                if char is None or char == "␀":
                    break
                characters.append(char)
                cursor += 2
            if characters:
                # Long padding runs separate screen fields but remain unchanged.
                text = "".join(characters)
                offset = 0
                while offset < len(text):
                    end = text.find("____", offset)
                    if end < 0:
                        end = len(text)
                    if end > offset:
                        value = text[offset:end]
                        a = segment_start + 2 * offset + HEADER_SIZE
                        z = a + 2 * len(value) - 1
                        result[f"{a:05X}={z:05X}"] = value
                    offset = end + 4
            cursor = max(cursor + 1, segment_start + 1)
    # Status and map names are NUL-delimited fixed fields. Keep every 8140
    # padding character up to the delimiter instead of splitting on spaces.
    for first, last in TEXT_RANGES[:2]:
        for key in list(result):
            if first <= int(key[:5], 16) <= last:
                del result[key]
        raw = decoded[first - HEADER_SIZE:last - HEADER_SIZE + 1]
        field_start = 0
        for cursor in range(len(raw) + 1):
            if cursor < len(raw) and raw[cursor] != 0:
                continue
            field = raw[field_start:cursor]
            if field:
                if len(field) % 2:
                    raise ValueError(f"odd-length text field at {first + field_start:05X}")
                chars = []
                for i in range(0, len(field), 2):
                    code = field[i:i + 2].hex().upper()
                    char = table.get_char(code)
                    if char is None:
                        raise ValueError(f"unknown text code {code} at {first + field_start + i:05X}")
                    chars.append(char)
                a = first + field_start
                z = a + len(field) - 1
                result[f"{a:05X}={z:05X}"] = "".join(chars)
            field_start = cursor + 1
    # Ending rows are fixed-width fields. The trailing 8140 bytes belong to
    # the row and may hold a longer Korean translation without moving code.
    for key in list(result):
        if ENDING_STARTS[0] <= int(key[:5], 16) < ENDING_STARTS[-1]:
            del result[key]
    for first, stop in zip(ENDING_STARTS, ENDING_STARTS[1:]):
        raw = decoded[first - HEADER_SIZE:stop - HEADER_SIZE]
        if len(raw) % 2:
            raise ValueError(f"ending row at {first:05X} has odd byte length")
        chars = []
        for i in range(0, len(raw), 2):
            code = raw[i:i + 2].hex().upper()
            char = table.get_char(code)
            if char is None:
                raise ValueError(f"ending row {first:05X}: unknown code {code}")
            chars.append(char)
        result[f"{first:05X}={stop - 1:05X}"] = "".join(chars)
    return dict(sorted(result.items()))


def extract_mapped_text(decoded: bytes, table: FontTable,
                        address_map: dict[str, str]) -> dict[str, str]:
    """Read the 9A overlay's fields at verified positions from the 7B mapping."""
    result = {}
    for address in address_map.values():
        first, last = (int(part, 16) for part in address.split("="))
        raw = decoded[first - HEADER_SIZE:last - HEADER_SIZE + 1]
        if len(raw) != last - first + 1 or len(raw) % 2:
            raise ValueError(f"invalid mapped END.BIN field at {address}")
        chars = []
        for offset in range(0, len(raw), 2):
            code = raw[offset:offset + 2].hex().upper()
            char = table.get_char(code)
            if char is None:
                raise ValueError(f"unknown text code {code} at {first + offset:05X}")
            chars.append(char)
        result[address] = "".join(chars)
    return dict(sorted(result.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--replace-draft", action="store_true", help="regenerate fields while preserving existing Korean edits")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    source = (workspace / "jpn-pc98" / "END.BIN").read_bytes()
    decoded = decompress(source)
    table = FontTable(FONT_PATH, workspace / "script-pc98" / "custom_char.json")
    if source[2] == 0x9A:
        map_path = Path(__file__).resolve().parent / "end_bin_7B_to_9A_addresses.json"
        if not map_path.exists():
            raise ValueError(f"9A END.BIN address map is missing: {map_path}")
        document = extract_mapped_text(decoded, table, json.loads(map_path.read_text(encoding="utf-8")))
    else:
        document = extract_text(decoded, table)
    if not document:
        raise ValueError("no END.BIN text was extracted")
    script_dir = workspace / "script-pc98"
    script_dir.mkdir(parents=True, exist_ok=True)
    jpn_path = script_dir / "END.BIN_decoded_jpn.json"
    kor_path = script_dir / "END.BIN_decoded_kor.json"
    if args.replace_draft:
        if not jpn_path.exists() or not kor_path.exists():
            raise ValueError("existing decoded JSON pair is missing")
        old_jpn = json.loads(jpn_path.read_text(encoding="utf-8"))
        old_kor = json.loads(kor_path.read_text(encoding="utf-8"))
        if list(old_jpn) != list(old_kor):
            raise ValueError("existing Japanese/Korean keys differ")
        kor_document = dict(document)
        migrated: set[str] = set()
        for new_key, japanese in document.items():
            new_start, new_end = (int(part, 16) for part in new_key.split("="))
            result = list(japanese)
            for old_key, old_text in old_jpn.items():
                old_start, old_end = (int(part, 16) for part in old_key.split("="))
                if not (new_start <= old_start <= old_end <= new_end):
                    continue
                migrated.add(old_key)
                translation = old_kor[old_key]
                if old_key == new_key:
                    if old_text != japanese:
                        raise ValueError(f"Japanese source changed at {old_key}")
                    result = list(translation)
                    continue
                if translation == old_text:
                    continue
                if "|" in translation or len(translation) * 2 != old_end - old_start + 1:
                    raise ValueError(f"cannot automatically migrate {old_key}")
                offset = (old_start - new_start) // 2
                result[offset:offset + len(translation)] = translation
            kor_document[new_key] = "".join(result)
        if migrated != set(old_jpn):
            raise ValueError(f"unmapped old text fields: {sorted(set(old_jpn) - migrated)}")
    else:
        kor_document = document
    for name in ("END.BIN_decoded_jpn.json", "END.BIN_decoded_kor.json"):
        path = script_dir / name
        if path.exists() and not args.replace_draft:
            raise FileExistsError(f"refusing to overwrite {path}")
        content = kor_document if name.endswith("_kor.json") else document
        path.write_text(json.dumps(content, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
        print(path, len(document))


if __name__ == "__main__":
    main()
