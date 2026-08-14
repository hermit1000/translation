import json
from pathlib import Path


WORKSPACE = Path("c:/work_han/workspace5")
SRC_PATH = Path("font_table/font_table-jpn-nb5-kanji-kor.tsv")
JPN_OUTPUT = WORKSPACE / "script-pc98/custom_word_ext_jpn.json"
KOR_OUTPUT = WORKSPACE / "script-pc98/custom_word_ext_kor.json"
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


def kanji_code_to_stored_code(code: str) -> str:
    code_int = int(code, 16)
    row = (code_int >> 8) & 0xFF
    cell = code_int & 0xFF

    lead = ((row + 1) // 2) + 0x70
    if lead >= 0xA0:
        lead += 0x40

    if row % 2:
        trail = cell + 0x1F
        if trail >= 0x7F:
            trail += 1
    else:
        trail = cell + 0x7E

    return f"{lead:02X}{trail:02X}"


def load_rows(path: Path) -> list[tuple[str, str, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        columns = line.split("\t")
        if len(columns) < 3:
            raise ValueError(f"Invalid row: {line}")
        code, japanese, korean = columns[:3]
        rows.append((code, japanese.strip(), korean.strip()))
    return rows


def build_tables(rows: list[tuple[str, str, str]]) -> tuple[dict[str, str], dict[str, str]]:
    jpn_words = {}
    kor_words = {}
    code_by_japanese = {}
    for code, japanese, korean in rows:
        stored_code = kanji_code_to_stored_code(code)
        if japanese:
            code_by_japanese[japanese] = stored_code
        if japanese:
            if japanese in jpn_words:
                raise ValueError(f"Duplicated Japanese ext word: {japanese}")
            jpn_words[japanese] = stored_code
        if korean:
            key = f"{japanese}:{korean}" if japanese else korean
            if key in kor_words:
                raise ValueError(f"Duplicated Korean ext word: {key}")
            kor_words[key] = stored_code
        elif japanese:
            key = japanese
            if key in kor_words:
                raise ValueError(f"Duplicated Korean ext word: {key}")
            kor_words[key] = stored_code

    for source, target in KOR_EXT_PHRASES.items():
        if len(source) != len(target):
            raise ValueError(f"Phrase replacement must keep glyph count: {source} -> {target}")
        for source_char, target_char in zip(source, target):
            stored_code = code_by_japanese.get(source_char)
            if stored_code is None:
                raise ValueError(f"Missing Japanese ext char for phrase: {source_char}")
            kor_words[f"{source_char}:{target_char}"] = stored_code

    return jpn_words, kor_words


def write_json(path: Path, data: dict[str, str]) -> None:
    path = resolve_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\r\n") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main() -> None:
    rows = load_rows(SRC_PATH)
    jpn_words, kor_words = build_tables(rows)
    write_json(JPN_OUTPUT, jpn_words)
    write_json(KOR_OUTPUT, kor_words)
    print(f"{resolve_path(JPN_OUTPUT)}: {len(jpn_words)} entries")
    print(f"{resolve_path(KOR_OUTPUT)}: {len(kor_words)} entries")


if __name__ == "__main__":
    main()
