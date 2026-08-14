"""NB5 MAIN.EXE에서 KANJI.NB5 외자 코드 문자열만 별도 추출한다."""

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from module.font_table import FontTable
from module.script import Script


DEFAULT_WORKSPACE = Path("c:/work_han/workspace5")
DEFAULT_BASE_FONT_TABLE = Path("font_table/font_table-jpn.json")
DEFAULT_NB5_KANJI_TABLE = Path("font_table/font_table-jpn-nb5-kanji.json")
DEFAULT_SCAN_START = 0x47000
EXT_CODE_RANGES = ((0x7621, 0x767E), (0x7721, 0x777E))
EXCLUDED_CODES = {"776C", "776D", "776E", "776F"}
ALLOWED_1BYTE_CHARS = set("_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz%")
KNOWN_TEXT_RANGES = (
    (0x4BE91, 0x4BEAC),
    (0x60FB8, 0x60FC1),
    (0x62BE0, 0x62D2B),
    (0x62F96, 0x62FAD),
    (0x63D2B, 0x63D35),
    (0x602D0, 0x602D9),
    (0x640FF, 0x64137),
    (0x6433C, 0x64344),
    (0x645A6, 0x645B6),
    (0x648D0, 0x64922),
    (0x64D34, 0x64FED),
)
SPECIAL_SUFFIX_ENTRIES = ("実|_|_行", "|%|4|d年|%|3|d月")


def is_ext_code(code: str) -> bool:
    if code in EXCLUDED_CODES:
        return False
    code_int = int(code, 16)
    return any(start <= code_int <= end for start, end in EXT_CODE_RANGES)


def jis_code_to_sjis_code(code: str) -> str:
    """Convert a KANJI.NB5 display code such as 776C to the stored bytes."""
    code_int = int(code, 16)
    row = (code_int >> 8) & 0xFF
    cell = code_int & 0xFF

    lead = ((row + 1) // 2) + 0x70
    if lead >= 0xA0:
        lead += 0x40

    if row % 2:
        trail = cell + 0x1F
        if trail >= 0x7F:
            trail += 1
    else:
        trail = cell + 0x7E

    return f"{lead:02X}{trail:02X}"


def load_nb5_kanji_table(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_ext_chars(path: Path) -> set[str]:
    table = load_nb5_kanji_table(path)
    return {character for code, character in table.items() if is_ext_code(code)}


def load_merged_font_table(base_path: Path, ext_path: Path) -> FontTable:
    font_table = FontTable(base_path)
    ext_table = {
        jis_code_to_sjis_code(code): character
        for code, character in load_nb5_kanji_table(ext_path).items()
        if is_ext_code(code)
    }
    font_table.set_custom_char(ext_table)
    return font_table


def has_private_use_char(text: str) -> bool:
    return any(0xE000 <= ord(character) <= 0xF8FF for character in text)


def has_noisy_1byte_char(text: str) -> bool:
    i = 0
    while i < len(text):
        if text[i] != "|":
            i += 1
            continue
        i += 1
        if i >= len(text):
            return True
        if text[i] not in ALLOWED_1BYTE_CHARS:
            return True
        i += 1
    return False


def is_likely_noise(text: str) -> bool:
    if has_private_use_char(text):
        return True
    if has_noisy_1byte_char(text):
        return True
    return False


def is_in_known_text_range(address: str) -> bool:
    start, end = (int(value, 16) for value in address.split("="))
    return any(range_start <= start and end <= range_end for range_start, range_end in KNOWN_TEXT_RANGES)


def recover_special_suffix_entries(script: Script, font_table: FontTable) -> dict[str, str]:
    recovered = {}
    for address, content in script.script.items():
        start, _ = (int(value, 16) for value in address.split("="))
        text = content.text
        for suffix in SPECIAL_SUFFIX_ENTRIES:
            suffix_start = text.find(suffix)
            if suffix_start < 0:
                continue
            prefix = text[:suffix_start]
            recovered_start = start + font_table.check_length_from_sentence(prefix)
            recovered_length = font_table.check_length_from_sentence(suffix)
            recovered_address = f"{recovered_start:05X}={recovered_start + recovered_length - 1:05X}"
            if is_in_known_text_range(recovered_address):
                recovered[recovered_address] = suffix
    return recovered


def output_path_for(workspace: Path) -> Path:
    return workspace / "script-pc98" / "MAIN.EXE_jpn_ext.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workspace",
        nargs="?",
        type=Path,
        default=DEFAULT_WORKSPACE,
        help=f"작업공간 경로 (기본값: {DEFAULT_WORKSPACE})",
    )
    parser.add_argument(
        "--base-font-table",
        type=Path,
        default=DEFAULT_BASE_FONT_TABLE,
        help=f"기본 일본어 폰트 테이블 (기본값: {DEFAULT_BASE_FONT_TABLE})",
    )
    parser.add_argument(
        "--nb5-kanji-table",
        type=Path,
        default=DEFAULT_NB5_KANJI_TABLE,
        help=f"NB5 KANJI.NB5 외자 테이블 (기본값: {DEFAULT_NB5_KANJI_TABLE})",
    )
    parser.add_argument(
        "--scan-start",
        type=lambda value: int(value, 0),
        default=DEFAULT_SCAN_START,
        help=f"MAIN.EXE에서 외자 문자열을 찾기 시작할 offset (기본값: 0x{DEFAULT_SCAN_START:X})",
    )
    parser.add_argument(
        "--include-ascii",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="외자 주변 1바이트 문자까지 함께 추출한다. 기본값: True",
    )
    parser.add_argument(
        "--filter-noise",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="반각 가나/private-use 문자가 섞인 노이즈 후보를 제외한다. 기본값: True",
    )
    parser.add_argument(
        "--filter-known-ranges",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="확인된 MAIN.EXE 외자 메뉴/테이블 주소 구간만 남긴다. 기본값: True",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    source = args.workspace / "jpn-pc98" / "MAIN.EXE"
    if not source.is_file():
        parser.error(f"missing source file: {source}")

    font_table = load_merged_font_table(args.base_font_table, args.nb5_kanji_table)
    ext_chars = load_ext_chars(args.nb5_kanji_table)

    script = Script()
    script.extract_script(
        data=bytearray(source.read_bytes()),
        font_table=font_table,
        length_threshold=2,
        check_ascii=args.include_ascii,
        check_ascii_restriction=False,
    )

    filtered = {
        address: content.serialize()
        for address, content in script.script.items()
        if int(address.split("=")[0], 16) >= args.scan_start
        and any(character in ext_chars for character in content.text)
        and (not args.filter_noise or not is_likely_noise(content.text))
        and (not args.filter_known_ranges or is_in_known_text_range(address))
    }
    filtered.update(recover_special_suffix_entries(script, font_table))
    filtered = dict(sorted(filtered.items()))

    output_path = output_path_for(args.workspace)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\r\n") as file:
        json.dump(filtered, file, ensure_ascii=False, indent=4)
        file.write("\n")

    print(f"{source} -> {output_path} ({len(filtered)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
