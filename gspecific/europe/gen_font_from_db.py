import cv2
import json
from PIL import Image
from pathlib import Path
from module.font_table import FontTable
from module.font_image import set_2byte_merge, set_font


def main():
    base_dir = Path("c:/work_han/font_update_db")
    font_table = FontTable(Path("font_table/font_table-jpn.json"))

    font_name = "비스코"  # "비스코, 둥근모"

    if font_name == "비스코":
        src_font_canvas_path = base_dir / "BISCO.bmp"
        dst_font_canvas_path = base_dir / "europe-BISCO.bmp"
    elif font_name == "둥근모":
        src_font_canvas_path = base_dir / "ThinDungGeunMo.bmp"
        dst_font_canvas_path = base_dir / "europe-ThinDungGeunMo.bmp"
    else:
        assert 0, f"Font name is not supported - {font_name}."

    src_font_canvas = cv2.imread(str(src_font_canvas_path), cv2.IMREAD_GRAYSCALE)

    letter_2byte = set()
    # Add custom word
    letter_2byte.add("맑음")
    letter_2byte.add("흐림")
    letter_2byte.add("안개")
    letter_2byte.add("폭풍")

    # weapon
    letter_2byte.add("엘리")  # 엘리판트
    letter_2byte.add("판트")
    letter_2byte.add("나스")  # 나스호른
    letter_2byte.add("호른")
    letter_2byte.add("브룸")  # 브룸베어
    letter_2byte.add("베어")
    letter_2byte.add("마울")  # 마울티어
    letter_2byte.add("티어")
    letter_2byte.add("세모")  # 세모벤테
    letter_2byte.add("벤테")
    letter_2byte.add("마틸")  # 마틸다
    letter_2byte.add("다-")
    letter_2byte.add("발렌")  # 발렌타인
    letter_2byte.add("타인")
    letter_2byte.add("크루")  # 크루세이더
    letter_2byte.add("세이")
    letter_2byte.add("더-")
    letter_2byte.add("스튜")  # 스튜어드
    letter_2byte.add("어드")
    letter_2byte.add("그랜")  # 그랜트
    letter_2byte.add("트_")
    letter_2byte.add("파이")  # 파이어플라이
    letter_2byte.add("어플")
    letter_2byte.add("라이")
    letter_2byte.add("파운")  # 파운드
    letter_2byte.add("드_")
    letter_2byte.add("소뮤")  # 소뮤아S
    letter_2byte.add("아S")

    letter_2byte = list(letter_2byte)
    letter_2byte.sort()
    print(len(letter_2byte))

    ret_code_dict = {}
    # Set 2byte letters
    letter_2byte = [[s, "default"] for s in letter_2byte]  # Change format
    start_code = "9540"  # 鼻
    code_dict, end_code = set_2byte_merge(
        base_dir,
        letter_2byte,
        font_table,
        src_font_canvas,
        start_code=start_code,
    )
    ret_code_dict |= code_dict

    # set 8byte letters
    input_cand_8byte = []
    input_cand_8byte.append(["로트미스트로프", font_name])
    input_cand_8byte.append(["바이언라인", font_name])
    input_cand_8byte.append(["로코소프스키", font_name])
    input_cand_8byte.append(["슈베펜부르크", font_name])
    input_cand_8byte.append(["에이브람스", font_name])
    input_cand_8byte.append(["비스마르크", font_name])
    input_cand_8byte.append(["브뤼노비치", font_name])
    input_cand_8byte.append(["아이젠하워", font_name])
    input_cand_8byte.append(["프라이버그", font_name])
    input_cand_8byte.append(["클라이스트", font_name])
    input_cand_8byte.append(["라펜슈타인", font_name])
    input_cand_8byte.append(["라이헤나우", font_name])
    input_cand_8byte.append(["룬트슈테트", font_name])
    input_cand_8byte.append(["스코르체니", font_name])
    input_cand_8byte.append(["바실렙스키", font_name])

    start_code = "959F"  # 福
    code_dict, end_code = set_font(
        base_dir,
        font_table,
        src_font_canvas,
        start_code,
        4,
        input_cand_8byte,
    )
    ret_code_dict |= code_dict

    # set 10byte letters
    input_cand_10byte = []
    input_cand_10byte.append(["나이츠브리지", font_name])
    input_cand_10byte.append(["베르호페니예", font_name])
    input_cand_10byte.append(["비르_베우이드", font_name])
    input_cand_10byte.append(["비르_엘_구비", font_name])
    input_cand_10byte.append(["비르_엘_하르마트", font_name])
    input_cand_10byte.append(["비르_엘_할레파", font_name])
    input_cand_10byte.append(["비르_하케임", font_name])
    input_cand_10byte.append(["빌레르_보카주", font_name])
    input_cand_10byte.append(["슈트라우스베르크", font_name])
    input_cand_10byte.append(["시디_레제그", font_name])
    input_cand_10byte.append(["시디_무프타", font_name])
    input_cand_10byte.append(["아이젠퓌텐슈타트", font_name])
    input_cand_10byte.append(["엘루엣_에_타마르", font_name])
    input_cand_10byte.append(["트루아비에르주", font_name])
    input_cand_10byte.append(["퓌르스텐발데", font_name])
    input_cand_10byte.append(["프랑크푸르트", font_name])
    input_cand_10byte.append(["프로호로프카", font_name])

    code_dict, end_code = set_font(
        base_dir,
        font_table,
        src_font_canvas,
        end_code,
        5,
        input_cand_10byte,
    )
    ret_code_dict |= code_dict

    # Save font canvas image
    pil_img = Image.fromarray(src_font_canvas)
    one_bit_img = pil_img.convert("1")
    one_bit_img.save(dst_font_canvas_path)
    with open(base_dir / "code.json", "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(ret_code_dict, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
