import json
import os
import sys

sys.path.append("./")
from pathlib import Path
from module.font_table import FontTable
from module.sound import hiragana_pronunciation


def resolve_path(path: Path) -> Path:
    if path.exists():
        return path
    path_text = str(path)
    if len(path_text) >= 3 and path_text[1:3] == ":/":
        wsl_path = Path("/mnt") / path_text[0].lower() / path_text[3:]
        if wsl_path.exists():
            return wsl_path
    return path


def load_custom_words(path: Path) -> dict:
    path = resolve_path(path)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_custom_word_path(ws_num: int, platform: str) -> Path:
    return Path(f"c:/work_han/workspace{ws_num}") / f"script-{platform}" / "custom_word.json"


def split_code_bytes(hex_value: str) -> list[str]:
    if len(hex_value) % 2:
        raise ValueError(f"Invalid hex length: {hex_value}")

    byte_codes = [hex_value[index : index + 2].upper() for index in range(0, len(hex_value), 2)]
    codes = []
    index = 0
    while index < len(byte_codes):
        code_int = int(byte_codes[index], 16)
        if 0x81 <= code_int <= 0x9F or 0xE0 <= code_int <= 0xFC:
            if index + 1 >= len(byte_codes):
                raise ValueError(f"Missing trailing byte in custom word code: {hex_value}")
            codes.append(byte_codes[index] + byte_codes[index + 1])
            index += 2
        else:
            codes.append(byte_codes[index])
            index += 1
    return codes


def get_codes_with_custom_words(sentence: str, font_table: FontTable, custom_words: dict) -> list[str]:
    codes_hex = []
    index = 0
    while index < len(sentence):
        character = sentence[index]
        if character == "{":
            end_index = sentence.find("}", index)
            if end_index == -1:
                raise ValueError(f"Missing closing brace in sentence: {sentence}")
            word = sentence[index + 1 : end_index]
            hex_value = custom_words.get(word)
            if hex_value is None:
                raise ValueError(f"Custom word '{{{word}}}' not found in custom_words.")
            codes_hex.extend(split_code_bytes(hex_value))
            index = end_index + 1
            continue

        if character == "|":
            index += 1
            if index >= len(sentence):
                raise ValueError(f"Trailing 1-byte marker in sentence: {sentence}")
            code_hex = font_table.get_code_ascii(sentence[index])
            if code_hex is None:
                raise ValueError(f"1-byte character '{sentence[index]}' is not in the font table.")
            codes_hex.append(code_hex)
            index += 1
            continue

        code_hex = font_table.get_code(character)
        if code_hex is None:
            raise ValueError(f"Character '{character}' is not in the font table.")
        codes_hex.append(code_hex)
        index += 1

    return codes_hex


def main():
    os.system("clear")
    font_table_kor = FontTable(Path("font_table/font_table-kor-jin.json"))
    font_table_jpn = FontTable(Path("font_table/font_table-jpn.json"))

    ws_num = 5
    platform = "pc98"
    custom_words = load_custom_words(get_custom_word_path(ws_num, platform))

    # Get a code or codes from a letter or letters
    script = "믹"
    sound = "에"
    codes_hex = get_codes_with_custom_words(script, font_table_kor, custom_words)
    # codes_hex = font_table_jpn.get_codes(script)
    print(codes_hex)
    if script:
        print(font_table_kor.check_length_from_sentence(script, custom_words=custom_words))

    jpn = ""
    if len(sound):
        for letter in sound:
            ch = hiragana_pronunciation.get(letter)
            if ch is None:
                print(letter)
            else:
                jpn += ch
        print(jpn)

    # 반각 체크
    # halfwidth = "|ﾌ|ﾞ|ﾘ|ﾀ|ｲ|".replace("|", "")
    # halfwidth = halfwidth.encode("cp932")  # 반각 '카타카나 가'
    # print(jisx0201_to_unicode(halfwidth))
    # return

    hex_str = ""
    hex_str_rev = ""
    for code_hex in codes_hex:
        hex_str_rev += code_hex[2:]  # + " "
        hex_str_rev += code_hex[:2]  # + " "
        hex_str_rev += " "
        hex_str += code_hex
        hex_str += " "

    print(hex_str)
    # print(hex_str_rev)

    jpn_script = font_table_jpn.get_chars(codes_hex)
    # jpn_script = font_table_kor.get_chars(codes_hex)
    print(jpn_script + jpn)


if __name__ == "__main__":
    main()
