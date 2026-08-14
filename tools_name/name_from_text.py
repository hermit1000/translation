"""텍스트 파일에서 인명 DB를 추가하거나 갱신한다.

입력 파일은 UTF-8로 저장하며 빈 줄을 넣지 않는다.

main() 형식(한 줄에 전체 이름 하나):
    일본성 일본이름 - 한국성 한국이름

예:
    蛎崎 慶広 - 카키자키 요시히로
    葦名 盛氏 - 아시나 모리우지

파일 아래의 __main__ 블록에서 사용할 함수를 선택하고, 선택한 함수 안에서
game, ws_num과 입력 파일 경로를 설정한다.
DB 파일에 실제로 반영하려면 해당 함수 끝의 name_db.save_db() 주석을 해제한다.
"""

from module.name_db import NameDB
from module.name_codec import NamePair


def main():
    name_db = NameDB()
    game = "nb5"
    ws_num = 5
    base_dir = f"c:/work_han/workspace{ws_num}/ss.txt"
    with open(base_dir, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()

        jpn, kor = line.split("-")
        full_name_jpn = jpn.strip()
        full_name_kor = kor.strip()

        if "?" in full_name_kor:
            continue

        NamePair.parse(full_name_jpn)
        NamePair.parse(full_name_kor)
        name_info = name_db.get_full_name(full_name_jpn)
        if name_info is not None:
            print(full_name_jpn)
            if full_name_kor != name_info["kor"]:
                print(full_name_kor, name_info["kor"])

        name_db.add_full_name(full_name_jpn, full_name_kor, game)

    name_db.save_db()


if __name__ == "__main__":
    main()
