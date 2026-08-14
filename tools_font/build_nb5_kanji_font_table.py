import json
from pathlib import Path


SRC_PATH = Path("font_table/font_table-jpn-nb5-kanji-draft.tsv")
DST_PATH = Path("font_table/font_table-jpn-nb5-kanji.json")
EXCLUDED_CODES = {"776C", "776D", "776E", "776F"}


def main() -> None:
    rows = []
    for line in SRC_PATH.read_text(encoding="utf-8").splitlines()[1:]:
        code, character, confidence, *_ = line.split("\t")
        if confidence != "high":
            raise ValueError(f"{code} is not confirmed: {confidence}")
        if code in EXCLUDED_CODES:
            continue
        rows.append((code, character))

    table = dict(rows)
    with DST_PATH.open("w", encoding="utf-8", newline="\r\n") as file:
        json.dump(table, file, ensure_ascii=False, indent=2)
        file.write("\n")

    print(f"{DST_PATH}: {len(table)} entries")


if __name__ == "__main__":
    main()
