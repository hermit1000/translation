import sys
from pathlib import Path

sys.path.append("./")
from module.font_table import FontTable


def main():
    # Read a font table
    font_table_jpn = FontTable(Path("font_table/font_table-jpn.json"))
    # font_table_kor = FontTable(Path("font_table/font_table-kor-jin.json"))

    # Get a letter or letters from a code or codes
    code_txt = "B5 BF DB BC B2 BA C4 C6 A5 A5 A5"
    code_list = code_txt.split()
    word = ""
    i = 0
    while i < len(code_list):
        code_int = int(code_list[i], 16)
        if 0x81 <= code_int <= 0x9F or 0xE0 <= code_int <= 0xFC:
            code_hex = f"{code_list[i]}{code_list[i + 1]}".upper()
            character = font_table_jpn.get_char(code_hex)
            i += 2
        else:
            code_hex = code_list[i].upper()
            character = font_table_jpn.get_char_ascii(code_hex)
            i += 1
        word += character if character is not None else "@"
    # word = font_table_kor.get_chars(codes)
    print(word)


if __name__ == "__main__":
    main()
