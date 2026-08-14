"""NB5 이름 스크립트의 성명 항목을 NameDB의 한국어 코드로 치환한다.

`extract_nb5_name_scripts.py`가 생성한 `script-pc98/*_jpn.json`을 입력으로
받아 대응하는 `*_kor.json`을 생성/갱신한다. 성/명 포맷은 NB4에서 쓰던
"이름 앞 공백 우선" 규칙을 차용한다.

MAIN.EXE의 지역명 테이블은 region_db.json을 참고해 함께 치환한다. 여성
이름 같은 단독 이름 테이블은 치환하지 않는다.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from module.content import Content
from module.name_codec import (
    align_encoded_length,
    clean_script_name,
    format_korean_name_prefer_given_leading_space,
)
from module.name_db import NameDB
from module.script import Script

from gspecific.nobu5.extract_nb5_name_scripts import (
    DEFAULT_WORKSPACE,
    FAMILY_OFFSET,
    FIELD_SIZE,
    GIVEN_OFFSET,
    MAIN_PERSON_RECORD_COUNT,
    MAIN_PERSON_RECORD_SIZE,
    MAIN_PERSON_TABLE_OFFSET,
    MAIN_CASTLE_NAME_OFFSET,
    MAIN_CASTLE_NAME_SIZE,
    MAIN_CASTLE_RECORD_COUNT,
    MAIN_CASTLE_RECORD_SIZE,
    MAIN_CASTLE_TABLE_OFFSET,
    SN_CASTLE_NAME_OFFSET,
    RECORD_SIZE,
    SN_CASTLE_RECORD_COUNT,
    SN_CASTLE_RECORD_SIZE,
    SN_CASTLE_TABLE_OFFSET,
    SN_CASTLE_NAME_SIZE,
    SN_GARBLED_REGION_PREFIXES,
    SN_NAME_LAYOUTS,
    SN_REGION_SCAN_START,
    SN_RECORD_SIZE,
    SN_TARGET_FILE_NAMES,
    SN_XOR_KEY,
)


GAME = "nb5"
NB5_TARGETS = tuple(f"S{index}T.NB5" for index in range(5))
MAIN_TARGET = "MAIN.EXE"
MAIN_NAME_TARGET = "MAIN.EXE.name"
SN_TARGETS = SN_TARGET_FILE_NAMES
DEFAULT_REGION_DB = Path("name_db/region_db.json")
REGION = [
    "나가토",
    "도토미",
    "리쿠츄",
    "무사시",
    "미카와",
    "사누키",
    "사츠마",
    "사카이",
    "스루가",
    "시모사",
    "야마토",
    "아즈치",
    "에치젠",
    "오와리",
    "이나바",
    "이와미",
    "이즈미",
    "코즈케",
    "키요스",
    "타지마",
    "하리마",
    "히타치",
]


@dataclass(frozen=True)
class NamePairEntry:
    family_address: str
    given_address: str
    field_size: int


def parse_address(address: str) -> Tuple[int, int]:
    start, end = address.split("=")
    return int(start, 16), int(end, 16)


def address_length(address: str) -> int:
    start, end = parse_address(address)
    return end - start + 1


def address_for(start: int, length: int) -> str:
    return f"{start:05X}={start + length - 1:05X}"


def output_path_for_jpn(jpn_path: Path) -> Path:
    name = jpn_path.name
    if not name.endswith("_jpn.json"):
        raise ValueError(f"Unexpected script file name: {jpn_path}")
    return jpn_path.with_name(name.removesuffix("_jpn.json") + "_kor.json")


def clone_script(script: Script) -> Script:
    cloned = Script()
    cloned.zero_padding = script.zero_padding
    cloned.encoding = script.encoding
    cloned.custom_input = script.custom_input
    cloned.binary_input = script.binary_input
    cloned.add_script({address: content.serialize() for address, content in script.script.items()})
    return cloned


def apply_target_metadata(script_name: str, script: Script) -> None:
    if script_name in SN_TARGETS and script.encoding is None:
        script.encoding = f"xor:0x{SN_XOR_KEY:02X}"


def has_game(entry: dict, game: str) -> bool:
    games = entry.get("game", [])
    if isinstance(games, str):
        games = [games]
    return game in games


def normalize_region_text(text: str) -> str:
    for suffix in ("산성", "섬", "산"):
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def load_region_db(region_db_path: Path, game: str = GAME) -> Dict[str, str]:
    with open(region_db_path, "r", encoding="utf-8") as file:
        region_db = json.load(file)

    regions = {}
    for japanese, entry in region_db.items():
        if isinstance(entry, str):
            continue
        if has_game(entry, game):
            regions[japanese] = entry["kor"]
    return regions


def format_region_code(region: str) -> Tuple[str, int]:
    if len(region) == 2:
        return region, 4

    if region in REGION:
        return f"{{{region}}}", 4

    suffix = ""
    for candidate in ("산성", "섬", "산"):
        if region.endswith(candidate):
            suffix = candidate
            region = region[: -len(candidate)]
            break

    pairs = []
    for index in range(0, len(region), 2):
        pair = region[index : index + 2]
        if len(pair) == 1:
            pair += "_"
        pairs.append(pair)
    code = "".join(f"{{{pair}}}" for pair in pairs)
    if suffix:
        code += suffix

    return code, len(pairs) * 2 + len(suffix) * 2


def trim_prefixed_region_key(region: str, region_db: Dict[str, str]) -> Tuple[int, str]:
    if region in region_db:
        return 0, region
    if region and region[0] in SN_GARBLED_REGION_PREFIXES:
        suffix = region[1:]
        if suffix in region_db:
            return 2, suffix
    return 0, region


def display_name(content: Content) -> str:
    if content.is_hex:
        if content.description is None:
            return content.text
        return content.description.strip()
    return clean_script_name(content.text)


def pad_to_length(text: str, current_length: int, target_length: int) -> str:
    if current_length > target_length:
        raise ValueError(f"current_length({current_length}) > target_length({target_length})")
    difference = target_length - current_length
    if difference == 0:
        return text
    text += "␀" * (difference // 2)
    if difference % 2:
        text += "|␀"
    return text


def align_name_field(
    source_content: Content,
    source_name: str,
    source_length: int,
    target_code: str,
    target_length: int,
) -> Tuple[int, str, str]:
    if source_content.is_hex:
        if target_length > source_length:
            raise ValueError(
                f"{source_content.serialize()} cannot be expanded from {source_length} to {target_length} bytes"
            )
        return source_length, source_content.serialize(), pad_to_length(target_code, target_length, source_length)

    return align_encoded_length(source_name, target_code, source_length, target_length)


def source_name_length(content: Content, clean_name: str, address: str) -> int:
    if content.is_hex:
        return address_length(address)
    return len(clean_name) * 2


def iter_nb5_pairs(script: Script) -> Iterable[NamePairEntry]:
    addresses = set(script.script)
    starts = {parse_address(address)[0]: address for address in addresses}

    for family_address in sorted(addresses, key=lambda item: parse_address(item)[0]):
        family_start, _ = parse_address(family_address)
        record_start = family_start - FAMILY_OFFSET
        if record_start < 0 or record_start % RECORD_SIZE != 0:
            continue
        given_start = record_start + GIVEN_OFFSET
        given_address = starts.get(given_start)
        if given_address is None:
            continue
        yield NamePairEntry(family_address, given_address, FIELD_SIZE)


def iter_sn_pairs(script: Script) -> Iterable[NamePairEntry]:
    addresses = set(script.script)
    starts = {parse_address(address)[0]: address for address in addresses}

    for family_address in sorted(addresses, key=lambda item: parse_address(item)[0]):
        family_start, _ = parse_address(family_address)
        for family_offset, given_offset in SN_NAME_LAYOUTS:
            record_start = family_start - family_offset
            if record_start < 0 or record_start % SN_RECORD_SIZE != 0:
                continue
            given_start = record_start + given_offset
            given_address = starts.get(given_start)
            if given_address is None:
                continue
            yield NamePairEntry(family_address, given_address, FIELD_SIZE)


def iter_main_person_pairs(script: Script) -> Iterable[NamePairEntry]:
    starts = {parse_address(address)[0]: address for address in script.script}

    for record_index in range(MAIN_PERSON_RECORD_COUNT):
        record_start = MAIN_PERSON_TABLE_OFFSET + record_index * MAIN_PERSON_RECORD_SIZE
        family_address = starts.get(record_start + FAMILY_OFFSET)
        given_address = starts.get(record_start + GIVEN_OFFSET)
        if family_address is None and given_address is None:
            continue
        if family_address is None or given_address is None:
            raise ValueError(f"incomplete MAIN.EXE person-name pair at 0x{record_start:05X}")
        yield NamePairEntry(family_address, given_address, FIELD_SIZE)


def iter_name_pairs(script_name: str, script: Script) -> Iterable[NamePairEntry]:
    if script_name in {MAIN_TARGET, MAIN_NAME_TARGET}:
        return iter_main_person_pairs(script)
    if script_name in SN_TARGETS:
        return iter_sn_pairs(script)
    return iter_nb5_pairs(script)


def replace_name_pair(
    script_name: str,
    script_jpn: Script,
    script_kor: Script,
    pair: NamePairEntry,
    name_db: NameDB,
    unknown_names: List[str],
) -> bool:
    family_content = script_jpn.script[pair.family_address]
    given_content = script_jpn.script[pair.given_address]

    family_jpn = display_name(family_content)
    given_jpn = display_name(given_content)
    full_name_jpn = f"{family_jpn} {given_jpn}"

    korean_name = name_db.get_korean_name(full_name_jpn, GAME)
    if korean_name is None:
        unknown_names.append(f"{script_name}: {full_name_jpn}")
        return False

    family_code, given_code, family_length_kor, given_length_kor = format_korean_name_prefer_given_leading_space(
        korean_name.family,
        korean_name.given,
        max_length=pair.field_size,
    )

    family_length_jpn = source_name_length(family_content, family_jpn, pair.family_address)
    given_length_jpn = source_name_length(given_content, given_jpn, pair.given_address)

    family_length, family_jpn_aligned, family_code_aligned = align_name_field(
        family_content,
        family_jpn,
        family_length_jpn,
        family_code,
        family_length_kor,
    )
    given_length, given_jpn_aligned, given_code_aligned = align_name_field(
        given_content,
        given_jpn,
        given_length_jpn,
        given_code,
        given_length_kor,
    )

    family_start, _ = parse_address(pair.family_address)
    given_start, _ = parse_address(pair.given_address)
    family_address_new = address_for(family_start, family_length)
    given_address_new = address_for(given_start, given_length)

    script_jpn.replace_sentence(pair.family_address, family_address_new, family_jpn_aligned)
    script_kor.replace_sentence(pair.family_address, family_address_new, family_code_aligned)
    script_jpn.replace_sentence(pair.given_address, given_address_new, given_jpn_aligned)
    script_kor.replace_sentence(pair.given_address, given_address_new, given_code_aligned)
    return True


def iter_main_region_addresses(script: Script) -> Iterable[str]:
    starts = {parse_address(address)[0]: address for address in script.script}

    for record_index in range(MAIN_CASTLE_RECORD_COUNT):
        start = MAIN_CASTLE_TABLE_OFFSET + record_index * MAIN_CASTLE_RECORD_SIZE + MAIN_CASTLE_NAME_OFFSET
        address = starts.get(start)
        if address is not None:
            yield address


def iter_sn_region_addresses(script: Script) -> Iterable[str]:
    pair_addresses = {
        address
        for pair in iter_sn_pairs(script)
        for address in (pair.family_address, pair.given_address)
    }
    starts = {parse_address(address)[0]: address for address in script.script}

    yielded = set()
    for record_index in range(SN_CASTLE_RECORD_COUNT):
        start = SN_CASTLE_TABLE_OFFSET + record_index * SN_CASTLE_RECORD_SIZE + SN_CASTLE_NAME_OFFSET
        address = starts.get(start)
        if address is None or address in pair_addresses:
            continue
        yielded.add(address)
        yield address

    for address in sorted(script.script, key=lambda item: parse_address(item)[0]):
        start, _ = parse_address(address)
        if start < SN_REGION_SCAN_START:
            continue
        if address in pair_addresses:
            continue
        if address in yielded:
            continue
        yield address


def replace_region(
    script_name: str,
    script_jpn: Script,
    script_kor: Script,
    address: str,
    region_db: Dict[str, str],
    unknown_regions: List[str],
    max_length: int,
) -> bool:
    content = script_jpn.script[address]
    japanese_region = display_name(content)
    skipped, japanese_region = trim_prefixed_region_key(japanese_region, region_db)
    korean_region = region_db.get(japanese_region)
    if korean_region is None:
        unknown_regions.append(f"{script_name}: {japanese_region}")
        return False

    region_code, region_length = format_region_code(korean_region)
    source_length = source_name_length(content, japanese_region, address)
    if region_length > max_length:
        raise ValueError(f"{script_name} region is too long: {japanese_region} -> {region_code}")

    length, jpn_aligned, region_code_aligned = align_name_field(
        content,
        japanese_region,
        source_length,
        region_code,
        region_length,
    )

    start, _ = parse_address(address)
    start += skipped
    new_address = address_for(start, length)
    script_jpn.replace_sentence(address, new_address, jpn_aligned)
    script_kor.replace_sentence(address, new_address, region_code_aligned)
    return True


def replace_regions(
    script_name: str,
    script_jpn: Script,
    script_kor: Script,
    region_db: Dict[str, str],
) -> Tuple[int, List[str]]:
    if script_name in {MAIN_TARGET, MAIN_NAME_TARGET}:
        region_addresses = list(iter_main_region_addresses(script_jpn))
        max_length = MAIN_CASTLE_NAME_SIZE
    elif script_name in SN_TARGETS:
        region_addresses = list(iter_sn_region_addresses(script_jpn))
        max_length = SN_CASTLE_NAME_SIZE
    else:
        return 0, []

    unknown_regions: List[str] = []
    replaced_count = 0
    for address in region_addresses:
        if replace_region(script_name, script_jpn, script_kor, address, region_db, unknown_regions, max_length):
            replaced_count += 1

    return replaced_count, unknown_regions


def process_script(
    script_name: str,
    jpn_path: Path,
    kor_path: Path,
    name_db: NameDB,
    region_db: Dict[str, str],
) -> Tuple[int, int, List[str], List[str], Script, Script]:
    script_jpn = Script(str(jpn_path))
    script_kor = Script(str(kor_path)) if kor_path.exists() else clone_script(script_jpn)
    apply_target_metadata(script_name, script_jpn)
    apply_target_metadata(script_name, script_kor)

    unknown_names: List[str] = []
    replaced_count = 0
    for pair in list(iter_name_pairs(script_name, script_jpn)):
        if replace_name_pair(script_name, script_jpn, script_kor, pair, name_db, unknown_names):
            replaced_count += 1

    replaced_region_count, unknown_regions = replace_regions(script_name, script_jpn, script_kor, region_db)

    return replaced_count, replaced_region_count, unknown_names, unknown_regions, script_jpn, script_kor


def resolve_targets(workspace: Path) -> List[Tuple[str, Path, Path]]:
    script_dir = workspace / "script-pc98"
    targets: List[Tuple[str, Path, Path]] = []

    missing = []
    for file_name in (*NB5_TARGETS, *SN_TARGETS):
        jpn_path = script_dir / f"{file_name}_jpn.json"
        if not jpn_path.is_file():
            missing.append(jpn_path)
            continue
        targets.append((file_name, jpn_path, output_path_for_jpn(jpn_path)))

    if missing:
        raise FileNotFoundError("Missing input scripts: " + ", ".join(str(path) for path in missing))

    main_jpn_path = script_dir / "MAIN.EXE_jpn.json"
    if main_jpn_path.is_file():
        targets.append((MAIN_TARGET, main_jpn_path, output_path_for_jpn(main_jpn_path)))

    main_jpn_path = script_dir / "MAIN.EXE.name_jpn.json"
    if main_jpn_path.is_file():
        targets.append((MAIN_NAME_TARGET, main_jpn_path, output_path_for_jpn(main_jpn_path)))

    return targets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workspace",
        nargs="?",
        type=Path,
        default=DEFAULT_WORKSPACE,
        help=f"script-pc98가 있는 작업공간 경로 (기본값: {DEFAULT_WORKSPACE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="결과 파일을 저장하지 않고 변환 가능 여부만 확인한다.",
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
    name_db = NameDB()
    region_db = load_region_db(args.region_db)

    try:
        targets = resolve_targets(args.workspace)
    except FileNotFoundError as exc:
        parser.error(str(exc))

    all_unknown_names: List[str] = []
    all_unknown_regions: List[str] = []
    for script_name, jpn_path, kor_path in targets:
        try:
            replaced_count, replaced_region_count, unknown_names, unknown_regions, script_jpn, script_kor = process_script(
                script_name,
                jpn_path,
                kor_path,
                name_db,
                region_db,
            )
        except ValueError as exc:
            parser.error(f"{jpn_path}: {exc}")

        all_unknown_names.extend(unknown_names)
        all_unknown_regions.extend(unknown_regions)
        if not args.dry_run:
            script_jpn.save(str(jpn_path))
            script_kor.save(str(kor_path))

        action = "checked" if args.dry_run else "wrote"
        print(
            f"{jpn_path} -> {kor_path} "
            f"({action}, {replaced_count} name pairs, {replaced_region_count} regions)"
        )

    if all_unknown_names:
        print("Unknown names:")
        for name in all_unknown_names:
            print(f"  {name}")

    if all_unknown_regions:
        print("Skipped regions without region_db entries:")
        for region in all_unknown_regions:
            print(f"  {region}")

    return 1 if all_unknown_names else 0


if __name__ == "__main__":
    raise SystemExit(main())
