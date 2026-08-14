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


def main() -> None:
    ws_num = 4
    platform = "pc98"
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

    occurrence_counts: Counter[str] = Counter()
    sentence_counts: Counter[str] = Counter()
    file_counts: Counter[str] = Counter()

    kor_files = sorted(script_base_dir.glob("*_kor.json"))
    for kor_path in kor_files:
        with kor_path.open("r", encoding="utf-8") as f:
            sentences = list(iter_sentences(json.load(f)))

        keys_used_in_file: set[str] = set()
        for sentence in sentences:
            for key in custom_words:
                placeholder = "{" + key + "}"
                count = sentence.count(placeholder)
                if count:
                    occurrence_counts[key] += count
                    sentence_counts[key] += 1
                    keys_used_in_file.add(key)

        for key in keys_used_in_file:
            file_counts[key] += 1

    sorted_keys = sorted(
        custom_words,
        key=lambda key: (-occurrence_counts[key], -sentence_counts[key], key),
    )

    print(f"대상 파일: {len(kor_files)}개")
    print(f"custom_word 키: {len(custom_words)}개")
    print("키\t등장 횟수\t문장 수\t파일 수")
    for key in sorted_keys:
        print(f"{key}\t{occurrence_counts[key]}\t{sentence_counts[key]}\t{file_counts[key]}")


if __name__ == "__main__":
    main()
