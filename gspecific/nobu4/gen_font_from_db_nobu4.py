import cv2
import json
from PIL import Image
from pathlib import Path
from module.name_db import NameDB
from module.font_table import FontTable
from module.font_image import add_text_pairs, imread_korean, return_img_roi_1byte, set_2byte_merge, set_font


TARGET_GAME = "nb4"


REGIONS = [
    # "도토미",
    # "무사시",
    # "미카와",
    # "사가미",
    # "사누키",
    # "사츠마",
    # "스루가",
    # "시나노",
    # "시모사",
    # "야마토",
    # "오와리",
    # "에치고",
    # "에치젠",
    # "이나바",
    # "이와미",
    # "이즈모",
    # "코즈케",
    # "토야마",
    # "하리마",
    # "히타치",
]


def has_game(entry: dict, game: str) -> bool:
    games = entry.get("game", [])
    if isinstance(games, str):
        games = [games]
    return game in games


def iter_region_texts(region_db: dict, game: str):
    for entry in region_db.values():
        if isinstance(entry, str):
            text = entry
            is_san_entry = False
        else:
            if not has_game(entry, game):
                continue
            text = entry["kor"]
            is_san_entry = "jpn" in entry

        if is_san_entry:
            if text[-2:] == "산성":
                text = text[:-2]
            if text[-1] in ["산", "성"]:
                text = text[:-1]
        elif text in REGIONS:
            continue

        yield text


def iter_nb4_region_texts(region_db: dict):
    yield from iter_region_texts(region_db, TARGET_GAME)


def main():
    base_dir = Path("c:/work_han/font_update_db")
    db_dir = Path("C:/work_han/translation/name_db")

    font_name = "비스코"
    font_file = "BISCO.bmp"
    font_table = FontTable(Path("font_table/font_table-jpn.json"))
    src_font_canvas_path = base_dir / font_file
    src_font_canvas = cv2.imread(str(src_font_canvas_path), cv2.IMREAD_GRAYSCALE)

    # 1byte font
    input_cand_1byte = []
    input_cand_1byte += ["|가", "|갓", "|게", "|겐", "|고", "|기"]
    input_cand_1byte += ["|나", "|노", "|니"]
    input_cand_1byte += ["|다", "|도"]
    input_cand_1byte += ["|라", "|레", "|로", "|리", "|린"]
    input_cand_1byte += ["|마", "|메", "|모", "|미"]
    input_cand_1byte += ["|바", "|베", "|보"]
    input_cand_1byte += ["|사", "|센", "|스", "|시"]
    input_cand_1byte += ["|야", "|야", "|에", "|엔", "|오", "|와", "|유", "|이", "|인"]
    input_cand_1byte += ["|저", "|젠", "|조", "|즈", "|지", "|츠", "|치"]
    input_cand_1byte += ["|카", "|케", "|쿠", "|키", "|타", "|테", "|텐", "|토", "|포"]
    input_cand_1byte += ["|호"]
    input_cand_1byte.sort()
    if len(input_cand_1byte) > 58:
        print(len(input_cand_1byte))
        return

    start_code_int = 0xA6
    ret_code_dict = {letter: f"{start_code_int + i:02X}" for i, letter in enumerate(input_cand_1byte)}

    for i, letter in enumerate(input_cand_1byte):
        roi = return_img_roi_1byte(hex(start_code_int + i))
        font_path = base_dir / "byte1" / f"{letter.replace('|', '')}.bmp"
        if not font_path.exists():
            print(f"{font_path} does not exist.")
            continue
        kor_font = imread_korean(font_path)
        src_font_canvas[roi[0] : roi[1], roi[2] : roi[3]] = kor_font

    letter_2byte = set()

    # Name
    db = NameDB()
    for _, korean_name, _ in db.iter_name_pairs("nb4"):
        family_name, given_name = korean_name.family, korean_name.given
        if len(family_name) > 6 or len(given_name) > 6:
            print(korean_name)
            continue

        if len(family_name) % 2:
            family_name += "_"
        if len(given_name) % 2:
            given_name = "_" + given_name

        add_text_pairs(family_name, letter_2byte)
        add_text_pairs(given_name, letter_2byte)

    # Region
    with open(db_dir / "region_db.json", "r", encoding="utf-8") as f:
        region_db = json.load(f)
        for text in iter_nb4_region_texts(region_db):
            space = add_text_pairs(text, letter_2byte)
            if space:
                print(1)

    # 다기
    with open(db_dir / "nb4" / "nb4_다기.json", "r", encoding="utf-8") as f:
        san_db = json.load(f)
        for k, v in san_db.items():
            kor = v["kor"].replace(" ", "")
            space = add_text_pairs(kor, letter_2byte)
            if space:
                print(1)

    # 추가
    letter_2byte.add("니혼")
    letter_2byte.add("데와")
    letter_2byte.add("아즈")
    letter_2byte.add("센노")
    letter_2byte.add("리큐")
    letter_2byte.add("츠다")
    letter_2byte.add("소큐")
    letter_2byte.add("소닌")
    letter_2byte.add("시나")
    letter_2byte.add("유칸")
    letter_2byte.add("카노")
    letter_2byte.add("에이")
    letter_2byte.add("유쇼")
    letter_2byte.add("산라")
    letter_2byte.add("키쿠")
    letter_2byte.add("테이")

    # Remove pairs that can be represented entirely with 1-byte fonts.
    letter_1byte = {letter.removeprefix("|") for letter in input_cand_1byte}

    def can_use_1byte(pair: str) -> bool:
        if len(pair) != 2:
            return False

        first, second = pair
        if first == "_":
            return second in letter_1byte
        if second == "_":
            return first in letter_1byte
        return first in letter_1byte and second in letter_1byte

    letter_2byte = {pair for pair in letter_2byte if not can_use_1byte(pair)}
    letter_2byte = list(letter_2byte)
    letter_2byte.sort()
    print(len(letter_2byte))

    start_code = "9540"  # 鼻

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
    code_dict, next_code = set_font(base_dir, font_table, src_font_canvas, start_code, 1, input_cand)
    ret_code_dict |= code_dict

    # set 4byte letters
    input_cand = []
    input_cand.append(["다이묘", font_name])
    input_cand.append(["와-과", font_name])
    input_cand.append(["은-는", font_name])
    input_cand.append(["을-를", font_name])
    input_cand.append(["이-가", font_name])

    for region in REGIONS:
        input_cand.append([region, font_name])

    code_dict, next_code = set_font(base_dir, font_table, src_font_canvas, next_code, 2, input_cand)
    ret_code_dict |= code_dict

    # set 6byte letters
    input_cand = []
    input_cand.append(["여름은밤", font_name])
    code_dict, next_code = set_font(base_dir, font_table, src_font_canvas, next_code, 3, input_cand)
    ret_code_dict |= code_dict

    # set 8byte letters
    input_cand = []
    input_cand.append(["가을은저녁", font_name])
    code_dict, next_code = set_font(base_dir, font_table, src_font_canvas, next_code, 4, input_cand)
    ret_code_dict |= code_dict

    # Set merged 2byte letters
    letter_2byte = [[s, "default"] for s in letter_2byte]  # Change format
    code_dict, _ = set_2byte_merge(base_dir, letter_2byte, font_table, src_font_canvas)

    code_dict["야마우치"] = "EBB3"
    code_dict["후카야"] = "EBB4"

    ret_code_dict |= dict(sorted(code_dict.items()))

    # Save font canvas image
    dst_font_canvas_path = base_dir / f"nobu4-{font_file}"
    pil_img = Image.fromarray(src_font_canvas)
    one_bit_img = pil_img.convert("1")
    one_bit_img.save(dst_font_canvas_path)
    with open(base_dir / "custom_word.json", "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(ret_code_dict, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
