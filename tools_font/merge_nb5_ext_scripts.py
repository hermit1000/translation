import json
import argparse
from pathlib import Path


WORKSPACE = Path("c:/work_han/workspace5")
SCRIPT_DIR = WORKSPACE / "script-pc98"
EXT_WORD_PATH = SCRIPT_DIR / "custom_word_ext_jpn.json"
KOR_EXT_WORD_PATH = SCRIPT_DIR / "custom_word_ext_kor.json"
EXT_SCRIPT_PATH = SCRIPT_DIR / "MAIN.EXE_jpn_ext.json"
MAIN_SCRIPT_PATH = SCRIPT_DIR / "MAIN.EXE_jpn.json"
KOR_SCRIPT_PATH = SCRIPT_DIR / "MAIN.EXE_kor.json"
KOR_EXT_SCRIPT_PATH = SCRIPT_DIR / "MAIN.EXE_kor_ext.json"
KANJI_KOR_TABLE = Path("font_table/font_table-jpn-nb5-kanji-kor.tsv")
KOR_TEXT_REPLACEMENTS = {
    "最大": "최대",
}
KOR_EXT_PHRASES = {
    "領内巡検": "영내순찰",
    "作事改修": "공사수리",
    "築城普請": "축성공사",
    "工作": "공작",
}


def resolve_path(path: Path) -> Path:
    if path.exists():
        return path
    path_text = str(path)
    if len(path_text) >= 3 and path_text[1:3] == ":/":
        wsl_path = Path("/mnt") / path_text[0].lower() / path_text[3:]
        if wsl_path.exists() or wsl_path.parent.exists():
            return wsl_path
    return path


def load_json(path: Path) -> dict:
    with resolve_path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, data: dict) -> None:
    path = resolve_path(path)
    with path.open("w", encoding="utf-8", newline="\r\n") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
        file.write("\n")


def parse_address(address: str) -> tuple[int, int]:
    start, end = address.split("=")
    return int(start, 16), int(end, 16)


def overlaps(left: str, right: str) -> bool:
    left_start, left_end = parse_address(left)
    right_start, right_end = parse_address(right)
    return not (left_end < right_start or right_end < left_start)


def brace_ext_words(text: str, ext_words: dict[str, str]) -> str:
    words = sorted(ext_words, key=len, reverse=True)
    output = []
    index = 0
    while index < len(text):
        if text[index] == "{":
            end_index = text.find("}", index)
            if end_index == -1:
                output.append(text[index:])
                break
            output.append(text[index : end_index + 1])
            index = end_index + 1
            continue

        if text[index] == "|":
            output.append(text[index : index + 2])
            index += 2
            continue

        for word in words:
            if text.startswith(word, index):
                output.append(f"{{{word}}}")
                index += len(word)
                break
        else:
            output.append(text[index])
            index += 1

    return "".join(output)


def brace_ext_script(ext_script: dict, ext_words: dict[str, str]) -> dict:
    return {address: brace_ext_words(text, ext_words) for address, text in ext_script.items()}


def load_ext_kor_labels(path: Path) -> dict[str, str]:
    labels = {}
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        columns = line.split("\t")
        if len(columns) < 3:
            raise ValueError(f"Invalid row: {line}")
        _, japanese, korean = columns[:3]
        japanese = japanese.strip()
        korean = korean.strip()
        if japanese and korean:
            labels[japanese] = f"{japanese}:{korean}"
        elif japanese:
            labels[japanese] = japanese
    return labels


def convert_ext_jpn_to_kor(text: str, ext_kor_labels: dict[str, str]) -> str:
    for source, target in KOR_TEXT_REPLACEMENTS.items():
        text = text.replace(source, target)

    output = []
    index = 0
    while index < len(text):
        if text[index] != "{":
            output.append(text[index])
            index += 1
            continue

        phrase = match_braced_phrase(text, index, KOR_EXT_PHRASES)
        if phrase is not None:
            source, target, separators, end_index = phrase
            source_chars = list(source)
            target_chars = list(target)
            if len(source_chars) != len(target_chars):
                raise ValueError(f"Phrase replacement must keep glyph count: {source} -> {target}")
            for char_index, (source_char, target_char) in enumerate(zip(source_chars, target_chars)):
                output.append(f"{{{source_char}:{target_char}}}")
                if char_index < len(separators):
                    output.append(separators[char_index])
            index = end_index
            continue

        end_index = text.find("}", index)
        if end_index == -1:
            output.append(text[index:])
            break

        word = text[index + 1 : end_index]
        output.append(f"{{{ext_kor_labels.get(word, word)}}}")
        index = end_index + 1

    return "".join(output)


def match_braced_phrase(
    text: str,
    start_index: int,
    phrases: dict[str, str],
) -> tuple[str, str, list[str], int] | None:
    for source, target in sorted(phrases.items(), key=lambda item: len(item[0]), reverse=True):
        index = start_index
        separators = []
        matched = True
        for char_index, character in enumerate(source):
            expected = f"{{{character}}}"
            if not text.startswith(expected, index):
                matched = False
                break
            index += len(expected)
            if char_index == len(source) - 1:
                continue

            separator_start = index
            while index < len(text) and text[index] != "{":
                if text[index] == "|":
                    index += 2
                else:
                    matched = False
                    break
            if not matched:
                break
            separators.append(text[separator_start:index])
        if matched:
            return source, target, separators, index
    return None


def convert_ext_script_to_kor(ext_script: dict[str, str], ext_kor_labels: dict[str, str]) -> dict[str, str]:
    return {
        address: convert_ext_jpn_to_kor(text, ext_kor_labels)
        for address, text in ext_script.items()
    }


def merge_ext_script(main_script: dict, ext_script: dict) -> tuple[dict, list[str]]:
    metadata = {
        key: value
        for key, value in main_script.items()
        if "=" not in key
    }
    merged = {
        key: value
        for key, value in main_script.items()
        if "=" in key and not any(overlaps(key, ext_address) for ext_address in ext_script)
    }
    removed = [
        key
        for key in main_script
        if "=" in key and any(overlaps(key, ext_address) for ext_address in ext_script)
    ]
    merged.update(ext_script)
    return {**metadata, **dict(sorted(merged.items()))}, removed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge NB5 MAIN.EXE ext scripts.")
    parser.add_argument(
        "--target",
        choices=("jpn", "kor", "both"),
        default="both",
        help="병합 대상 (기본값: both)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    ext_words = load_json(EXT_WORD_PATH)
    ext_script = brace_ext_script(load_json(EXT_SCRIPT_PATH), ext_words)

    if args.target in {"jpn", "both"}:
        main_script = load_json(MAIN_SCRIPT_PATH)
        merged_script, removed = merge_ext_script(main_script, ext_script)
        write_json(EXT_SCRIPT_PATH, ext_script)
        write_json(MAIN_SCRIPT_PATH, merged_script)
        print(f"{resolve_path(EXT_SCRIPT_PATH)}: wrote {len(ext_script)} braced ext entries")
        print(
            f"{resolve_path(MAIN_SCRIPT_PATH)}: merged {len(ext_script)} ext entries, "
            f"removed {len(removed)} overlapping entries"
        )

    if args.target in {"kor", "both"}:
        ext_kor_labels = load_ext_kor_labels(KANJI_KOR_TABLE)
        kor_ext_script = convert_ext_script_to_kor(ext_script, ext_kor_labels)
        kor_script = load_json(KOR_SCRIPT_PATH)
        merged_kor_script, removed_kor = merge_ext_script(kor_script, kor_ext_script)
        write_json(KOR_EXT_SCRIPT_PATH, kor_ext_script)
        write_json(KOR_SCRIPT_PATH, merged_kor_script)
        print(f"{resolve_path(KOR_EXT_SCRIPT_PATH)}: wrote {len(kor_ext_script)} braced ext entries")
        print(
            f"{resolve_path(KOR_SCRIPT_PATH)}: merged {len(kor_ext_script)} ext entries, "
            f"removed {len(removed_kor)} overlapping entries"
        )


if __name__ == "__main__":
    main()
