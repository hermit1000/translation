import argparse
import json
from pathlib import Path


def is_odd_full_name(kor: str) -> bool:
    parts = kor.split()
    if len(parts) != 2:
        return False

    family_name, given_name = parts
    return len(family_name) % 2 == 1 and len(given_name) % 2 == 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--game",
        default="nb4",
        help="지정한 game tag가 포함된 항목만 출력한다. 예: nb4, taiko2",
    )
    args = parser.parse_args()

    repo_base_dir = Path(__file__).resolve().parents[1]
    name_db_path = repo_base_dir / "name_db" / "full_name_db.json"

    with name_db_path.open("r", encoding="utf-8") as f:
        full_name_db = json.load(f)

    if not isinstance(full_name_db, dict):
        raise ValueError(f"{name_db_path}의 최상위 값은 객체여야 합니다.")

    matches = []
    for jp_name, info in full_name_db.items():
        if not isinstance(info, dict):
            continue

        kor = info.get("kor")
        games = info.get("game", [])
        if not isinstance(kor, str) or not isinstance(games, list):
            continue

        if args.game is not None and args.game not in games:
            continue

        if is_odd_full_name(kor):
            matches.append((jp_name, kor, games))

    print(f"대상 항목: {len(full_name_db)}개")
    if args.game is not None:
        print(f'game tag "{args.game}" 필터 적용')
    print(f"조건 일치: {len(matches)}개")
    print("일본어명\t한국어명\tgame")
    for jp_name, kor, games in matches:
        print(f"{jp_name}\t{kor}\t{','.join(games)}")


if __name__ == "__main__":
    main()
