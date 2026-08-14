from pathlib import Path

from module.font_table import FontTable
from module.script import Script

if __package__:
    from .backward_check import CHECK_LETTERS, backward_check
else:
    from backward_check import CHECK_LETTERS, backward_check


FILTER_START = 0x38729
FILTER_END = 0x3DF33


def find_search_str(sentence: str):
    skip = False
    for letter in sentence:
        if skip:
            skip = False
            continue
        if letter == "|":
            skip = True
            continue
        if letter in CHECK_LETTERS:
            return letter
    return None


def main():
    ws_num = 1
    platform = "pc98"
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_dir = base_dir / f"script-{platform}"
    bin_dir = base_dir / f"jpn-{platform}"

    font_table = FontTable(
        file_path=Path("./font_table/font_table-jpn.json"),
        custom_char_path=script_dir / "custom_char.json",
    )
    consider_1byte = True

    for file in script_dir.rglob("*.json"):
        if "_jpn.json" not in file.name:
            continue

        if "MAIN.EXE" not in file.name:
            continue

        bin_path = bin_dir / file.name.replace("_jpn.json", "")
        if not bin_path.exists():
            print(f"No bin file found!: {bin_path}")
            continue

        with open(bin_path, "rb") as f:
            data = bytearray(f.read())

        script = Script(str(file))
        updates = []

        for address, content in script.script.items():
            if "=" not in address or content.is_hex:
                continue

            start, end = address.split("=", maxsplit=1)
            start_address = int(start, 16)
            end_address = int(end, 16)
            if not FILTER_START <= start_address <= FILTER_END:
                continue

            search_str = find_search_str(content.text)
            new_start, new_end, new_sentence = backward_check(
                data,
                start_address,
                end_address,
                font_table,
                search_str,
                consider_1byte,
            )
            new_address = f"{new_start:0{len(start)}X}={new_end:0{len(end)}X}"

            if new_address != address or new_sentence != content.text:
                updates.append((address, new_address, new_sentence))

        for address, new_address, new_sentence in updates:
            script.replace_sentence(address, new_address, new_sentence)

        output_path = file.with_name(f"{file.stem}_backward.json")
        script.save(output_path)
        print(f"Saved {output_path}: {len(updates)} updates")


if __name__ == "__main__":
    main()
