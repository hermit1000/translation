import json
import re
from pathlib import Path

from module.font_table import FontTable


TARGET_PATH = Path("c:/work_han/workspace5/script-pc98/MAIN.EXE_kor.json")
FONT_TABLE = Path("font_table/font_table-kor-jin.json")
EXT_WORD_PATTERN = re.compile(r"\{[^}:]+:([^}]+)\}")


def resolve_path(path: Path) -> Path:
    if path.exists():
        return path
    path_text = str(path)
    if len(path_text) >= 3 and path_text[1:3] == ":/":
        wsl_path = Path("/mnt") / path_text[0].lower() / path_text[3:]
        if wsl_path.exists() or wsl_path.parent.exists():
            return wsl_path
    return path


def address_length(address: str) -> int:
    start, end = address.split("=")
    return int(end, 16) - int(start, 16) + 1


def convert_text(text: str) -> str:
    return EXT_WORD_PATTERN.sub(r"\1", text)


def main() -> None:
    target_path = resolve_path(TARGET_PATH)
    with target_path.open("r", encoding="utf-8") as file:
        script = json.load(file)

    font_table = FontTable(FONT_TABLE)
    converted = 0
    skipped = 0
    for address, text in list(script.items()):
        if "=" not in address or not isinstance(text, str):
            continue
        if not EXT_WORD_PATTERN.search(text):
            continue

        new_text = convert_text(text)
        try:
            length = font_table.check_length_from_sentence(new_text)
        except ValueError:
            skipped += 1
            continue
        if length > address_length(address):
            skipped += 1
            continue

        script[address] = new_text
        converted += 1

    with target_path.open("w", encoding="utf-8", newline="\r\n") as file:
        json.dump(script, file, ensure_ascii=False, indent=4)
        file.write("\n")

    print(f"{target_path}: converted {converted}, skipped {skipped}")


if __name__ == "__main__":
    main()
