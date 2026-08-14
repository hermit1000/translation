"""NB5의 고정 길이 인명 바이너리에서 *_jpn.json을 생성한다.

S0T.NB5부터 S4T.NB5까지는 0x1E바이트 레코드로 구성된다. 각 레코드의
+0x04에는 성, +0x0B에는 이름이 있으며 두 필드는 각각 최대 6바이트다.
파일 마지막의 0x1E바이트는 인명 레코드가 아닌 종료 레코드다.

MAIN.EXE의 0x598C6~0x5F90B 구간에는 인물, 성/지역명, 여성 이름 테이블이
서로 다른 고정 길이 레코드로 저장되어 있다.

SN0.NB5부터 SN4.NB5까지는 원본에서는 XOR 0xB4로 마스킹되어 있다.
원본 jpn-pc98/SN*.NB5를 내부에서 디코딩한 뒤 시나리오별 인명을 추출한다.
SN*은 0x27바이트 레코드이고, 대부분 +0x13에 성, +0x1A에 이름이 있다.
선두 레코드에는 선택 화면 표시용으로 +0x08/+0x0F 이름 필드도 있다.

작업공간 경로를 인자로 받아 jpn-pc98의 S0T.NB5부터 S4T.NB5와
MAIN.EXE와 SN0.NB5부터 SN4.NB5를 고정 순서로 읽고, script-pc98에
대응하는 *_jpn.json을 만든다.
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Set, Tuple


RECORD_SIZE = 0x1E
FAMILY_OFFSET = 0x04
GIVEN_OFFSET = 0x0B
FIELD_SIZE = 6
FAMILY_TERMINATOR_OFFSET = 0x0A
GIVEN_TERMINATOR_OFFSET = 0x11
TRAILER = b"\x00\xFF\xFF" + b"\x00" * (RECORD_SIZE - 3)

MAIN_PERSON_TABLE_OFFSET = 0x598C2
MAIN_PERSON_RECORD_SIZE = 0x27
MAIN_PERSON_RECORD_COUNT = 460
MAIN_CASTLE_TABLE_OFFSET = 0x5DED6
MAIN_CASTLE_RECORD_SIZE = 0x26
MAIN_CASTLE_RECORD_COUNT = 173
MAIN_CASTLE_NAME_OFFSET = 0x06
MAIN_CASTLE_NAME_SIZE = 8
MAIN_WOMAN_TABLE_OFFSET = 0x5F884
MAIN_WOMAN_RECORD_SIZE = 0x0E
MAIN_WOMAN_RECORD_COUNT = 10
MAIN_WOMAN_NAME_OFFSET = 0x04
MAIN_WOMAN_NAME_SIZE = 8
MAIN_REQUIRED_SIZE = MAIN_WOMAN_TABLE_OFFSET + MAIN_WOMAN_RECORD_SIZE * MAIN_WOMAN_RECORD_COUNT

SN_RECORD_SIZE = 0x27
SN_REMAINDER_SIZE = 2
SN_FIELD_SIZE = 7
SN_NAME_LAYOUTS = ((0x08, 0x0F), (0x13, 0x1A))
SN_CASTLE_TABLE_OFFSET = 0x51FE
SN_CASTLE_RECORD_SIZE = 0x26
SN_CASTLE_RECORD_COUNT = 73
SN_CASTLE_NAME_OFFSET = 0x06
SN_CASTLE_NAME_SIZE = 8
SN_REGION_SCAN_START = 0x5C00
SN_REGION_SCAN_END = 0x6A00
SN_XOR_KEY = 0xB4
SN_GARBLED_REGION_PREFIXES = set("戞檬泥瓮絳羽薩襭錬魵")

SPECIAL_NAMES = {
    bytes.fromhex("EC8C EC8D EC8E"): "長宗我部",
    bytes.fromhex("EC8F EC8D EC8E"): "香宗我部",
}

TARGET_FILE_NAMES = tuple(f"S{index}T.NB5" for index in range(5)) + ("MAIN.EXE",)
SN_TARGET_FILE_NAMES = tuple(f"SN{index}.NB5" for index in range(5))
DEFAULT_WORKSPACE = Path("c:/work_han/workspace5")
DEFAULT_REGION_DB = Path("name_db/region_db.json")


def format_name(raw_name: bytes, name: str) -> str:
    if len(raw_name) != len(name) * 2:
        return f"0x:{raw_name.hex().upper()}# {name}"
    return name


def read_name_field(
    record: bytes,
    offset: int,
    field_size: int,
    source: Path,
    address: int,
    label: str,
    allow_empty: bool = False,
) -> Optional[Tuple[bytes, str]]:
    field = record[offset : offset + field_size]
    raw_name, separator, padding = field.partition(b"\x00")
    if not raw_name:
        if allow_empty and not any(field):
            return None
        raise ValueError(f"{source}: empty {label} name at 0x{address:05X}")
    if separator and any(padding):
        raise ValueError(f"{source}: non-zero {label} padding at 0x{address:05X}")

    special_name = SPECIAL_NAMES.get(raw_name)
    if special_name is not None:
        return raw_name, format_name(raw_name, special_name)

    try:
        return raw_name, format_name(raw_name, raw_name.decode("cp932"))
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"{source}: cannot decode {label} name at 0x{address:05X}: {raw_name.hex().upper()}"
        ) from exc


def add_name_entry(entries: Dict[str, str], address: int, raw_name: bytes, name: str) -> None:
    end = address + len(raw_name) - 1
    entries[f"{address:05X}={end:05X}"] = name


def extract_name_entries(data: bytes, source: Path) -> Dict[str, str]:
    if len(data) < RECORD_SIZE * 2 or len(data) % RECORD_SIZE:
        raise ValueError(f"{source}: file size must be a multiple of 0x{RECORD_SIZE:X}")
    if data[-RECORD_SIZE:] != TRAILER:
        raise ValueError(f"{source}: invalid trailing record")

    entries = {}
    record_count = len(data) // RECORD_SIZE - 1
    for record_index in range(record_count):
        record_start = record_index * RECORD_SIZE
        record = data[record_start : record_start + RECORD_SIZE]

        if record[FAMILY_TERMINATOR_OFFSET] != 0:
            raise ValueError(f"{source}: record {record_index} has no family-name terminator")
        if record[GIVEN_TERMINATOR_OFFSET] != 0:
            raise ValueError(f"{source}: record {record_index} has no given-name terminator")

        for label, offset in (("family", FAMILY_OFFSET), ("given", GIVEN_OFFSET)):
            start = record_start + offset
            result = read_name_field(record, offset, FIELD_SIZE, source, start, label)
            if result is None:
                raise AssertionError("NB5 name fields cannot be empty")
            raw_name, name = result
            add_name_entry(entries, start, raw_name, name)

    return entries


def extract_main_name_entries(data: bytes, source: Path) -> Dict[str, str]:
    if len(data) < MAIN_REQUIRED_SIZE:
        raise ValueError(f"{source}: MAIN.EXE is too small")

    entries = {}
    for record_index in range(MAIN_PERSON_RECORD_COUNT):
        record_start = MAIN_PERSON_TABLE_OFFSET + record_index * MAIN_PERSON_RECORD_SIZE
        record = data[record_start : record_start + MAIN_PERSON_RECORD_SIZE]
        if record[FAMILY_TERMINATOR_OFFSET] != 0 or record[GIVEN_TERMINATOR_OFFSET] != 0:
            raise ValueError(f"{source}: invalid person-name record at 0x{record_start:05X}")

        family = read_name_field(
            record,
            FAMILY_OFFSET,
            FIELD_SIZE,
            source,
            record_start + FAMILY_OFFSET,
            "family",
            allow_empty=True,
        )
        given = read_name_field(
            record,
            GIVEN_OFFSET,
            FIELD_SIZE,
            source,
            record_start + GIVEN_OFFSET,
            "given",
            allow_empty=True,
        )
        if family is None and given is None:
            continue
        if family is None or given is None:
            raise ValueError(f"{source}: incomplete person name at 0x{record_start:05X}")

        add_name_entry(entries, record_start + FAMILY_OFFSET, *family)
        add_name_entry(entries, record_start + GIVEN_OFFSET, *given)

    tables = (
        (
            "castle",
            MAIN_CASTLE_TABLE_OFFSET,
            MAIN_CASTLE_RECORD_SIZE,
            MAIN_CASTLE_RECORD_COUNT,
            MAIN_CASTLE_NAME_OFFSET,
            MAIN_CASTLE_NAME_SIZE,
        ),
        (
            "woman",
            MAIN_WOMAN_TABLE_OFFSET,
            MAIN_WOMAN_RECORD_SIZE,
            MAIN_WOMAN_RECORD_COUNT,
            MAIN_WOMAN_NAME_OFFSET,
            MAIN_WOMAN_NAME_SIZE,
        ),
    )
    for label, table_offset, record_size, record_count, name_offset, name_size in tables:
        for record_index in range(record_count):
            record_start = table_offset + record_index * record_size
            record = data[record_start : record_start + record_size]
            address = record_start + name_offset
            result = read_name_field(record, name_offset, name_size, source, address, label)
            if result is None:
                raise AssertionError("MAIN.EXE name fields cannot be empty")
            add_name_entry(entries, address, *result)

    return entries


def is_plausible_name(name: str) -> bool:
    return all(
        ("\u4e00" <= char <= "\u9fff")
        or ("\u3040" <= char <= "\u309f")
        or ("\u30a0" <= char <= "\u30ff")
        or char in "々ヶー"
        for char in name
    )


def try_read_sn_name_field(record: bytes, offset: int) -> Optional[Tuple[bytes, str]]:
    field = record[offset : offset + SN_FIELD_SIZE]
    raw_name, separator, padding = field.partition(b"\x00")
    if not raw_name:
        return None
    if separator and any(padding):
        return None

    special_name = SPECIAL_NAMES.get(raw_name)
    if special_name is not None:
        return raw_name, format_name(raw_name, special_name)

    try:
        name = raw_name.decode("cp932")
    except UnicodeDecodeError:
        return None
    if not is_plausible_name(name):
        return None
    return raw_name, format_name(raw_name, name)


def try_read_sn_region_field(record: bytes, offset: int, field_size: int) -> Optional[Tuple[bytes, str]]:
    field = record[offset : offset + field_size]
    raw_name, _, _ = field.partition(b"\x00")
    if not raw_name:
        return None

    special_name = SPECIAL_NAMES.get(raw_name)
    if special_name is not None:
        return raw_name, format_name(raw_name, special_name)

    try:
        name = raw_name.decode("cp932")
    except UnicodeDecodeError:
        return None
    if not is_plausible_name(name):
        return None
    return raw_name, format_name(raw_name, name)


def iter_cp932_japanese_runs(data: bytes, start: int, end: int) -> Iterator[Tuple[int, int, bytes, str]]:
    position = start
    limit = min(end, len(data))
    while position < limit - 1:
        run_start = position
        run_bytes = bytearray()
        run_text = []

        while position < limit - 1:
            chunk = data[position : position + 2]
            try:
                character = chunk.decode("cp932")
            except UnicodeDecodeError:
                break
            if len(character) != 1 or not is_plausible_name(character):
                break

            run_bytes.extend(chunk)
            run_text.append(character)
            position += 2

        if len(run_text) >= 2:
            yield run_start, position - 1, bytes(run_bytes), "".join(run_text)
        else:
            position = run_start + 1


def load_known_regions(region_db_path: Path) -> Set[str]:
    if not region_db_path.exists():
        return set()

    with open(region_db_path, "r", encoding="utf-8") as file:
        region_db = json.load(file)

    return set(region_db)


def trim_prefixed_region_run(raw_name: bytes, name: str, known_regions: Optional[Set[str]]) -> Tuple[int, bytes, str]:
    if known_regions is None or name in known_regions:
        return 0, raw_name, name

    if name and name[0] in SN_GARBLED_REGION_PREFIXES:
        suffix = name[1:]
        if suffix in known_regions:
            return 2, raw_name[2:], suffix

    return 0, raw_name, name


def decode_sn_data_if_needed(data: bytes, source: Path) -> bytes:
    if source.parent.name == "jpn-pc98-decoded":
        return data
    return bytes(byte ^ SN_XOR_KEY for byte in data)


def extract_sn_name_entries(data: bytes, source: Path, known_regions: Optional[Set[str]] = None) -> Dict[str, str]:
    data = decode_sn_data_if_needed(data, source)
    if len(data) % SN_RECORD_SIZE != SN_REMAINDER_SIZE:
        raise ValueError(
            f"{source}: decoded SN file size must be 0x{SN_RECORD_SIZE:X} records plus "
            f"{SN_REMAINDER_SIZE} bytes"
        )

    entries = {}
    record_count = len(data) // SN_RECORD_SIZE
    for record_index in range(record_count):
        record_start = record_index * SN_RECORD_SIZE
        record = data[record_start : record_start + SN_RECORD_SIZE]
        for family_offset, given_offset in SN_NAME_LAYOUTS:
            family = try_read_sn_name_field(record, family_offset)
            given = try_read_sn_name_field(record, given_offset)
            if family is None or given is None:
                continue
            add_name_entry(entries, record_start + family_offset, *family)
            add_name_entry(entries, record_start + given_offset, *given)

    for record_index in range(SN_CASTLE_RECORD_COUNT):
        record_start = SN_CASTLE_TABLE_OFFSET + record_index * SN_CASTLE_RECORD_SIZE
        record = data[record_start : record_start + SN_CASTLE_RECORD_SIZE]
        result = try_read_sn_region_field(record, SN_CASTLE_NAME_OFFSET, SN_CASTLE_NAME_SIZE)
        if result is None:
            continue
        add_name_entry(entries, record_start + SN_CASTLE_NAME_OFFSET, *result)

    for start, _, raw_name, name in iter_cp932_japanese_runs(data, SN_REGION_SCAN_START, SN_REGION_SCAN_END):
        skipped, raw_name, name = trim_prefixed_region_run(raw_name, name, known_regions)
        start += skipped
        add_name_entry(entries, start, raw_name, name)

    return entries


def extract_name_script(source: Path, known_regions: Optional[Set[str]] = None) -> Dict[str, str]:
    if not source.is_file():
        raise FileNotFoundError(source)
    data = source.read_bytes()
    if source.name.upper() == "MAIN.EXE":
        return extract_main_name_entries(data, source)
    if source.name.upper().startswith("SN") and source.suffix.upper() == ".NB5":
        return extract_sn_name_entries(data, source, known_regions)
    return extract_name_entries(data, source)


def output_path_for(source: Path, output_dir: Path) -> Path:
    if source.name.upper() == "MAIN.EXE":
        return output_dir / "MAIN.EXE.name_jpn.json"
    return output_dir / f"{source.name}_jpn.json"


def encoding_for_source(source: Path) -> Optional[str]:
    if source.name.upper().startswith("SN") and source.suffix.upper() == ".NB5":
        return f"xor:0x{SN_XOR_KEY:02X}"
    return None


def write_name_script(output_path: Path, entries: Dict[str, str], encoding: Optional[str] = None) -> None:
    output = {}
    if encoding is not None:
        output["encoding"] = encoding
    output.update(entries)
    with open(output_path, "w", encoding="utf-8", newline="\r\n") as file:
        json.dump(output, file, ensure_ascii=False, indent=4)


def resolve_sources(workspace_dir: Path) -> List[Path]:
    input_dir = workspace_dir / "jpn-pc98"
    sources = [input_dir / file_name for file_name in TARGET_FILE_NAMES]
    missing = [source for source in sources if not source.is_file()]
    if missing:
        raise FileNotFoundError("Missing input files: " + ", ".join(str(source) for source in missing))

    sn_sources = [input_dir / file_name for file_name in SN_TARGET_FILE_NAMES]
    missing_sn = [source for source in sn_sources if not source.is_file()]
    if missing_sn:
        decoded_input_dir = workspace_dir / "jpn-pc98-decoded"
        sn_sources = [decoded_input_dir / file_name for file_name in SN_TARGET_FILE_NAMES]
        missing_sn = [source for source in sn_sources if not source.is_file()]
        if missing_sn:
            raise FileNotFoundError("Missing SN input files: " + ", ".join(str(source) for source in missing_sn))
    sources.extend(sn_sources)
    return sources


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workspace",
        nargs="?",
        type=Path,
        default=DEFAULT_WORKSPACE,
        help=f"jpn-pc98와 script-pc98가 있는 작업공간 경로 (기본값: {DEFAULT_WORKSPACE})",
    )
    parser.add_argument(
        "--region-db",
        type=Path,
        default=DEFAULT_REGION_DB,
        help=f"지역명 DB JSON 경로 (기본값: {DEFAULT_REGION_DB})",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output_dir = args.workspace / "script-pc98"
    known_regions = load_known_regions(args.region_db)

    try:
        sources = resolve_sources(args.workspace)
        generated = [(source, extract_name_script(source, known_regions)) for source in sources]
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    output_paths = [output_path_for(source, output_dir) for source, _ in generated]
    output_dir.mkdir(parents=True, exist_ok=True)
    for (source, entries), output_path in zip(generated, output_paths):
        write_name_script(output_path, entries, encoding_for_source(source))
        print(f"{source} -> {output_path} ({len(entries)} entries)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
