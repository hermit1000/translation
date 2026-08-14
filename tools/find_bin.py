import re
import sys
from pathlib import Path

sys.path.append("./")
from module.font_table import FontTable
from module.decoding import decode


def main():
    ws_num = 5
    base_path = Path(f"../workspace{ws_num}/jpn-pc98")
    # base_path = Path(f"../workspace{ws_num}/kor-pc98-dosbox-x")
    # base_path = Path(f"../workspace{ws_num}/save")

    check_xor = False

    font_table_path = Path("font_table/font_table-kor-jin.json")
    font_table_path = Path("font_table/font_table-jpn.json")
    font_table = FontTable(font_table_path)

    sentence_to_find = "冥界の魔神"
    address_to_find_hex = font_table.get_codes(sentence_to_find)
    address_to_find_hex = "4E 50 4B".replace(" ", "")
    target_bytes = bytearray.fromhex("".join(address_to_find_hex))
    print(address_to_find_hex)

    sentence_to_replace = ""
    found_to_replace = False
    if len(sentence_to_replace) and not check_xor:
        address_to_replace_hex = font_table.get_codes(sentence_to_replace)
        replace_bytes = bytearray.fromhex("".join(address_to_replace_hex))

    for file in base_path.rglob("*"):  # Use rglob to search subdirectories
        if not file.is_file():
            continue
        # print(file.name)
        # if "MESS11" not in file.name:
        #     continue
        # if ".SV" not in file.name:
        #     continue

        with open(file, "rb") as f:
            raw_data = bytearray(f.read())

        if check_xor:
            for dc in range(0, 0xFF):
                decoding_info = f"xor:0x{dc:02X}"
                # Read a json script
                # print(file)
                data = decode(raw_data, decoding_info)
                position = data.find(target_bytes)

                if position != -1:
                    print(f"found a candidate file: {position:X} - {file}, xor:{dc:02X}")
        else:
            matches = re.finditer(re.escape(target_bytes), raw_data)
            positions = [match.start() for match in matches]
            for position in positions:
                print(f"found a candidate file: 0x{position:X} - {file}")

                if len(sentence_to_replace):
                    found_to_replace = True
                    raw_data[position : position + len(replace_bytes)] = replace_bytes

        if found_to_replace:
            with open(file, "wb") as f:
                f.write(raw_data)


if __name__ == "__main__":
    main()
