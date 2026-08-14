import json
from collections import Counter
from pathlib import Path
from typing import Iterator
from module.content import Content


def iter_sentences(script: dict) -> Iterator[str]:
    """메타데이터와 description을 제외한 대사 본문을 꺼낸다."""
    for address, sentence in script.items():
        if "=" not in address or not isinstance(sentence, str):
            continue
        yield Content.parse(sentence).text


def is_target_key(
    key: str,
    all_keys: set[str],
    check_left_only: bool,
    check_opposite_key: bool,
) -> bool:
    """선택한 형태와 상대 키 검사 조건에 맞는지 확인한다."""
    if len(key) <= 1:
        return False

    if check_left_only:
        if not key.startswith("_"):
            return False
        word = key[1:]
        opposite_key = f"{word}_"
    else:
        if not key.endswith("_"):
            return False
        word = key[:-1]
        opposite_key = f"_{word}"

    return not check_opposite_key or opposite_key not in all_keys


def main() -> None:
    ws_num = 1
    platform = "pc98"
    check_left_only = False  # True: _*, False: *_
    check_opposite_key = False  # True: 상대 키가 없는 항목만, False: 모두
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    if not base_dir.exists():
        # WSL에서 실행할 때의 C: 드라이브 경로
        base_dir = Path(f"/mnt/c/work_han/workspace{ws_num}")
    script_base_dir = base_dir / f"script-{platform}"

    custom_word_path = script_base_dir / "custom_word.json"
    with custom_word_path.open("r", encoding="utf-8") as f:
        custom_words = json.load(f)

    if not isinstance(custom_words, dict):
        raise ValueError(f"{custom_word_path}의 최상위 값은 객체여야 합니다.")

    all_keys = set(custom_words)
    target_keys = [key for key in custom_words if is_target_key(key, all_keys, check_left_only, check_opposite_key)]

    occurrence_counts: Counter[str] = Counter()
    sentence_counts: Counter[str] = Counter()
    file_counts: Counter[str] = Counter()

    kor_files = sorted(script_base_dir.glob("*_kor.json"))
    for kor_path in kor_files:
        with kor_path.open("r", encoding="utf-8") as f:
            sentences = list(iter_sentences(json.load(f)))

        keys_used_in_file: set[str] = set()
        for sentence in sentences:
            for key in target_keys:
                placeholder = "{" + key + "}"
                count = sentence.count(placeholder)
                if count:
                    occurrence_counts[key] += count
                    sentence_counts[key] += 1
                    keys_used_in_file.add(key)

        for key in keys_used_in_file:
            file_counts[key] += 1

    sorted_keys = sorted(
        target_keys,
        key=lambda key: (-occurrence_counts[key], -sentence_counts[key], key),
    )

    print(f"대상 파일: {len(kor_files)}개")
    print(f"custom_word 키: {len(custom_words)}개")
    key_pattern = "_*" if check_left_only else "*_"
    print(f'체크 대상 "{key_pattern}" 키: {len(target_keys)}개')
    print("키\t등장 횟수\t문장 수\t파일 수")
    for key in sorted_keys:
        print(f"{key}\t{occurrence_counts[key]}\t{sentence_counts[key]}\t{file_counts[key]}")

    alphabetical_keys = sorted(target_keys, key=lambda key: key.strip("_"))
    print("가나다순 키")
    print("".join(f"|{key}" for key in alphabetical_keys))


if __name__ == "__main__":
    main()
