"""Build a translated FQ3 END.BIN from END.BIN_decoded_kor.json.

Run: python build_end.py [workspace] [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from module.font_table import FontTable

from gspecific.fq.fq3.end_codec import HEADER_SIZE, compress, decompress, decompress_rle, patch_rle_literals
from gspecific.fq.fq3.extract_end import FONT_PATH

WORKSPACE_PATH = Path(r"C:\work_han\workspace13")
KOR_FONT_PATH = FONT_PATH.with_name("font_table-kor-jin.json")
BOLD_BRANCH = bytes.fromhex("2E F6 06 F8 01 80 74")


def encode(text: str, original: bytes, table: FontTable, jpn_table: FontTable,
           words: dict[str, str], address: str) -> bytes:
    output = bytearray()
    halfwidth = False
    cursor = 0
    while cursor < len(text):
        char = text[cursor]
        if char == "{":
            end = text.find("}", cursor + 1)
            if end < 0:
                raise ValueError(f"{address}: unclosed custom_word token")
            token = text[cursor + 1:end]
            code = words.get(token)
            if code is None:
                raise ValueError(f"{address}: missing custom_word glyph {token!r}")
            width = 1 if token.startswith("|") else 2
            if len(bytes.fromhex(code)) != width:
                raise ValueError(f"{address}: wrong code width for {token!r}: {code}")
            if halfwidth:
                raise ValueError(f"{address}: stray halfwidth marker before {token!r}")
            output.extend(bytes.fromhex(code))
            cursor = end + 1
            continue
        if char == "}":
            raise ValueError(f"{address}: unmatched closing brace")
        if char == "|" and not halfwidth:
            halfwidth = True
            cursor += 1
            continue
        code = table.get_code_ascii(char) if halfwidth else table.get_code(char)
        if code is None and not halfwidth:
            code = jpn_table.get_code(char)
        halfwidth = False
        if code is None:
            raise ValueError(f"{address}: character {char!r} is not in the Korean font table")
        output.extend(bytes.fromhex(code))
        cursor += 1
    if halfwidth:
        raise ValueError(f"{address}: trailing halfwidth marker")
    if len(output) != len(original):
        raise ValueError(f"{address}: {len(output)} bytes, expected {len(original)}")
    return bytes(output)


def build_bytes(workspace: Path) -> bytes:
    script_dir = workspace / "script-pc98"
    template = (workspace / "jpn-pc98" / "END.BIN").read_bytes()
    decoded = decompress(template)
    jpn_table = FontTable(FONT_PATH, script_dir / "custom_char.json")
    jpn_path = script_dir / "END.BIN_decoded_jpn.json"
    kor_path = script_dir / "END.BIN_decoded_kor.json"
    jpn = json.loads(jpn_path.read_text(encoding="utf-8"))
    kor = json.loads(kor_path.read_text(encoding="utf-8"))
    words = json.loads((script_dir / "custom_word.json").read_text(encoding="utf-8"))
    if list(kor) != list(jpn):
        raise ValueError("decoded Japanese and Korean JSON keys differ")
    for address, text in jpn.items():
        first, last = (int(part, 16) for part in address.split("="))
        original = decoded[first - HEADER_SIZE:last - HEADER_SIZE + 1]
        if encode(text, original, jpn_table, jpn_table, {}, address) != original:
            raise ValueError(f"Japanese source differs from END.BIN at {address}")
    table = FontTable(KOR_FONT_PATH, script_dir / "custom_char.json")
    patched = bytearray(decoded)
    for address, text in kor.items():
        if not isinstance(text, str):
            raise ValueError(f"{address}: translation must be a string")
        first, last = (int(part, 16) for part in address.split("="))
        start, stop = first - HEADER_SIZE, last - HEADER_SIZE + 1
        original = decoded[start:stop]
        if text == jpn[address]:
            continue  # Preserve the original Japanese bytes in the draft JSON.
        patched[start:stop] = encode(text, original, table, jpn_table, words, address)
    safe_image = patch_rle_literals(decoded, bytes(patched))
    if decompress_rle(safe_image) == decompress_rle(decoded):
        raise ValueError("translated END.BIN did not change the game-visible image")
    # END.BIN has its own font renderer. Bit 80h triggers SHR + OR to
    # thicken each scanline; JMP over that block in all three draw paths.
    if safe_image.count(BOLD_BRANCH) != 3:
        raise ValueError("END.BIN bold branch count differs from expected three")
    safe_image = safe_image.replace(BOLD_BRANCH, BOLD_BRANCH[:-1] + b"\xEB")
    decoded_overlay = decompress_rle(safe_image)
    if any(decoded_overlay[address] != 0xEB for address in (0xBB02, 0xBBBC, 0xBCBB)):
        raise ValueError("END.BIN thin-font branches did not reach expected locations")
    rebuilt = compress(safe_image, template)
    if len(rebuilt) > len(template):
        raise ValueError(
            f"rebuilt END.BIN is {len(rebuilt)} bytes; original is {len(template)}. "
            "The game's safe loader size is not established."
        )
    if decompress(rebuilt) != safe_image:
        raise ValueError("END.BIN compression round-trip failed")
    if decompress_rle(decompress(rebuilt)) != decompress_rle(safe_image):
        raise ValueError("END.BIN game decoder verification failed")
    return rebuilt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=WORKSPACE_PATH)
    parser.add_argument("--output", type=Path, help="default: workspace/kor-pc98/END.BIN")
    parser.add_argument("--check", action="store_true", help="verify without writing a binary")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    rebuilt = build_bytes(workspace)
    if args.check:
        print(f"END.BIN two-stage round-trip OK: {len(rebuilt)} bytes")
        return
    output = args.output or workspace / "kor-pc98" / "END.BIN"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(rebuilt)
    print(output, len(rebuilt))


if __name__ == "__main__":
    main()
