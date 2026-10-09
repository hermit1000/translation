"""NameDB의 NB5 인명에 필요한 한국어 폰트와 코드표를 생성한다.

`gspecific/nobu4/gen_font_from_db_nobu4.py`의 인명 처리 방식을 차용한다.
성명과 3글자 이상의 NB5 지역명을 대상으로 하며, 여성 단독 이름은 추후
필요할 때 별도로 추가한다.
"""

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence, Set

import cv2
from PIL import Image

from module.font_image import add_text_pairs, set_2byte_merge, set_font
from module.font_table import FontTable
from module.name_db import NameDB


DEFAULT_BASE_DIR = Path("c:/work_han/font_update_db")
DEFAULT_FONT_TABLE = Path("font_table/font_table-jpn.json")
DEFAULT_FONT_FILE = "BISCO.bmp"
DEFAULT_FONT_NAME = "비스코"
DEFAULT_REGION_DB = Path("name_db/region_db.json")
GAME = "nb5"
FIELD_SIZE = 6
REGION = [
    "나가토",
    "다지마",
    "도토미",
    "리쿠츄",
    "무사시",
    "미카와",
    "사가미",
    "사누키",
    "사츠마",
    "사카이",
    "스루가",
    "쓰시마",
    "시나노",
    "시모사",
    "야마토",
    "아와지",
    "아즈치",
    "에치고",
    "에치젠",
    "오오미",
    "오와리",
    "와카사",
    "이나바",
    "이와미",
    "이즈모",
    "이즈미",
    "치쿠고",
    "치쿠젠",
    "카와치",
    "카즈사",
    "코즈케",
    "키요스",
    "타지마",
    "하리마",
    "히타치",
]


def has_game(entry: dict, game: str) -> bool:
    games = entry.get("game", [])
    if isinstance(games, str):
        games = [games]
    return game in games


def collect_name_pairs(name_db: NameDB, game: str = GAME) -> Set[str]:
    letter_2byte: Set[str] = set()

    for _, korean_name, _ in name_db.iter_name_pairs(game):
        family_name = korean_name.family
        given_name = korean_name.given

        if len(family_name) > FIELD_SIZE or len(given_name) > FIELD_SIZE:
            print(f"{korean_name} is too long for NB5 name fields")
            continue

        # NB4/set_code_from_db_nobu5.py와 같은 성명 공백 규칙.
        if len(family_name) % 2:
            family_name += "_"
        if len(given_name) % 2:
            given_name = "_" + given_name

        add_text_pairs(family_name, letter_2byte)
        add_text_pairs(given_name, letter_2byte)

    return letter_2byte


def normalize_region_text(text: str) -> str:
    for suffix in ("산성", "섬", "산"):
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def collect_region_texts(region_db_path: Path, game: str = GAME) -> Set[str]:
    with open(region_db_path, "r", encoding="utf-8") as file:
        region_db = json.load(file)

    regions: Set[str] = set()
    for entry in region_db.values():
        if isinstance(entry, str):
            continue
        if not has_game(entry, game):
            continue

        text = entry["kor"]
        if len(text) < 3:
            continue

        regions.add(normalize_region_text(text))

    return regions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE_DIR,
        help=f"폰트 BMP와 byte1 글꼴 조각이 있는 경로 (기본값: {DEFAULT_BASE_DIR})",
    )
    parser.add_argument(
        "--font-table",
        type=Path,
        default=DEFAULT_FONT_TABLE,
        help=f"일본어 폰트 테이블 JSON 경로 (기본값: {DEFAULT_FONT_TABLE})",
    )
    parser.add_argument(
        "--font-file",
        default=DEFAULT_FONT_FILE,
        help=f"원본 폰트 캔버스 BMP 파일명 (기본값: {DEFAULT_FONT_FILE})",
    )
    parser.add_argument(
        "--output-prefix",
        default="nobu5",
        help="출력 BMP 파일 접두사 (기본값: nobu5)",
    )
    parser.add_argument(
        "--code-output",
        default="custom_word.json",
        help="생성할 코드표 JSON 파일명 (기본값: custom_word.json)",
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

    font_table = FontTable(args.font_table)
    src_font_canvas_path = args.base_dir / args.font_file
    src_font_canvas = cv2.imread(str(src_font_canvas_path), cv2.IMREAD_GRAYSCALE)
    if src_font_canvas is None:
        parser.error(f"Cannot read font canvas: {src_font_canvas_path}")

    font_name = DEFAULT_FONT_NAME
    letter_2byte = collect_name_pairs(NameDB())
    region_texts = collect_region_texts(args.region_db)
    region_4byte = [region for region in REGION if region in region_texts]
    region_2byte = region_texts - set(region_4byte)
    for region in region_2byte:
        add_text_pairs(region, letter_2byte)

    letter_2byte.add("맑음")
    letter_2byte.add("흐림")

    letter_2byte.add("_신")
    letter_2byte.add("게_")
    letter_2byte.add("고미")
    letter_2byte.add("고요")
    letter_2byte.add("구_")
    letter_2byte.add("다카")
    letter_2byte.add("리오")
    letter_2byte.add("리쿠")
    letter_2byte.add("리큐")
    letter_2byte.add("리키")
    letter_2byte.add("마치")
    letter_2byte.add("미미")
    letter_2byte.add("미카")
    letter_2byte.add("사부")
    letter_2byte.add("세토")
    letter_2byte.add("센노")
    letter_2byte.add("소큐")
    letter_2byte.add("소탄")
    letter_2byte.add("슈고")
    letter_2byte.add("스리")
    letter_2byte.add("시라")
    letter_2byte.add("와테")
    letter_2byte.add("오케")
    letter_2byte.add("이인")
    letter_2byte.add("제이")
    letter_2byte.add("즈노")
    letter_2byte.add("차야")
    letter_2byte.add("츠케")
    letter_2byte.add("쿠모")
    letter_2byte.add("쿠시")
    letter_2byte.add("키즈")
    letter_2byte.add("키쿠")
    letter_2byte.add("테이")
    letter_2byte.add("하자")
    letter_2byte.add("호쿠")

    print(len(letter_2byte))
    letter_2byte = sorted(letter_2byte)

    start_code = "9540"  # 鼻
    ret_code_dict = dict()
    input_cand = []
    input_cand.append(["은", font_name])
    input_cand.append(["는", font_name])
    input_cand.append(["이", font_name])
    input_cand.append(["가", font_name])
    input_cand.append(["을", font_name])
    input_cand.append(["를", font_name])
    input_cand.append(["와", font_name])
    input_cand.append(["과", font_name])
    input_cand.append(["에", font_name])
    input_cand.append(["의", font_name])
    input_cand.append(["국", font_name])
    code_dict, next_code = set_font(args.base_dir, font_table, src_font_canvas, start_code, 1, input_cand)
    ret_code_dict |= code_dict

    # set 4byte letters
    input_cand = []
    input_cand.append(["다이묘", font_name])
    input_cand.append(["와-과", font_name])
    input_cand.append(["은-는", font_name])
    input_cand.append(["을-를", font_name])
    input_cand.append(["이-가", font_name])
    input_cand.append(["이-라", font_name])
    input_cand.append(["에서", font_name])

    input_cand.extend([region, font_name] for region in region_4byte)

    code_dict, next_code = set_font(args.base_dir, font_table, src_font_canvas, next_code, 2, input_cand)
    ret_code_dict |= code_dict

    input_cand = [[letter, "default"] for letter in letter_2byte]
    code_dict, next_code = set_2byte_merge(
        args.base_dir,
        input_cand,
        font_table,
        src_font_canvas,
    )

    ret_code_dict |= dict(sorted(code_dict.items()))
    print(f"Final code: {next_code}")

    dst_font_canvas_path = args.base_dir / f"{args.output_prefix}-{args.font_file}"
    pil_img = Image.fromarray(src_font_canvas)
    one_bit_img = pil_img.convert("1")
    one_bit_img.save(dst_font_canvas_path)

    with open(args.base_dir / args.code_output, "w", encoding="utf-8", newline="\r\n") as file:
        json.dump(ret_code_dict, file, ensure_ascii=False, indent=4)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
