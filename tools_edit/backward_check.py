from pathlib import Path
from rich.console import Console
from module.script import Script
from module.font_table import FontTable


# Check letters
CHECK_LETTERS = ["！", "？", "。", "、", "あ", "を", "と", "い", "の", "か", "り", "ま", "パ", "よ"]


def is_sjis_lead_byte(byte_val: int) -> bool:
    """Checks if a byte is a Shift-JIS lead byte."""
    return (0x81 <= byte_val <= 0x9F) or (0xE0 <= byte_val <= 0xFC)


def backward_check(
    data: bytearray,
    start_address: int,
    end_address: int,
    font_table: FontTable,
    search_str: str = None,
    consider_1byte: bool = True,
):
    """
    Finds the true start of a sentence within a data range and returns the full sentence
    from that start to the original end_address.
    If search_str is provided, it's used as an anchor to start the backward search.
    """

    # Helper for forward decoding the final byte range
    def _decode_forward(sub_data: bytearray, consider_1byte: bool) -> str:
        sentence = ""
        i = 0
        while i < len(sub_data):
            # 2-byte char check
            if i + 1 < len(sub_data) and is_sjis_lead_byte(sub_data[i]):
                code_int = (sub_data[i] << 8) | sub_data[i + 1]
                char = font_table.get_char(f"{code_int:X}")
                if char:
                    sentence += char
                    i += 2
                    continue

            # 1-byte char check
            if consider_1byte:
                code_int = sub_data[i]
                char = font_table.get_char_ascii(f"{code_int:02X}")
                if char:
                    sentence += "|" + char
                elif 0x20 <= code_int <= 0x7E:
                    # Fallback for simple ASCII not in the font table
                    sentence += chr(code_int)
                else:
                    sentence += "?"  # Placeholder for other unmapped bytes
                i += 1
        return sentence

    # --- Step 1: Determine where the backward scan should start from ---
    scan_start_pos = end_address
    if search_str:

        def _str_to_bytes(s: str) -> bytearray:
            codes = font_table.get_codes(s)
            b = bytearray()
            for code in codes:
                if code:
                    b.extend(bytes.fromhex(code))
            return b

        search_bytes = _str_to_bytes(search_str)
        if search_bytes:
            found_idx = data.find(search_bytes, start_address, end_address + 1)
            if found_idx != -1:
                scan_start_pos = found_idx + len(search_bytes) - 1

    # --- Step 2: Scan backwards from scan_start_pos to find the true sentence start ---
    pos = scan_start_pos
    final_start_address = start_address  # Default to the original start

    # This loop is only to find the final_start_address
    temp_pos = pos
    while temp_pos >= start_address:
        is_char_found = False
        # Try to parse a 2-byte character ending at temp_pos
        if temp_pos > start_address and is_sjis_lead_byte(data[temp_pos - 1]):
            code_int = (data[temp_pos - 1] << 8) | data[temp_pos]
            if font_table.get_char(f"{code_int:X}"):
                temp_pos -= 2
                is_char_found = True

        if consider_1byte:
            if not is_char_found:
                # Try to parse a 1-byte character at temp_pos
                code_int = data[temp_pos]
                if font_table.get_char_ascii(f"{code_int:02X}") or (0x20 <= code_int <= 0x7E):
                    temp_pos -= 1
                    is_char_found = True

        if not is_char_found:
            # Hit a boundary (not a valid char), so the sentence started at temp_pos + 1
            final_start_address = temp_pos + 1
            break  # Exit the while loop

    if temp_pos < start_address:
        # Loop finished without hitting a boundary, sentence starts at the beginning of the range
        final_start_address = start_address

    # --- Step 3: Decode the final sentence and return ---
    final_sentence_data = data[final_start_address : end_address + 1]
    final_sentence = _decode_forward(final_sentence_data, consider_1byte)

    return final_start_address, end_address, final_sentence


def main():
    ws_num = 1
    platform = "pc98"
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_dir = base_dir / f"script-{platform}"
    bin_dir = base_dir / f"jpn-{platform}-decoded"

    script_path = script_dir / "MAIN.EXE_jpn.json"
    script_path = script_dir / "EVENT.EVT_jpn.json"

    bin_path = bin_dir / script_path.name.replace("_jpn.json", "")
    if not bin_path.exists():
        print(f"No bin file found!: {bin_path}")
        return
    with open(bin_path, "rb") as f:
        bin = f.read()
        bin = bytearray(bin)

    console = Console()
    font_table = FontTable(
        file_path=Path("./font_table/font_table-jpn.json"),
        custom_char_path=script_dir / "custom_char.json",
    )
    consider_1byte = True
    overwrite = False
    # overwrite = True

    source_array = {
        "268D0=26928": "|a|ﾚ|a|ｩ|a|r|`|4|`|#|`|ｷ|`チ|O|8|8いったい、どうすればいいって言うんだ。|I|Z世界を救う方法は、おれ達が|C",
    }

    dialogue_array = {
        "268D0=26928": "|a|ﾚ|a|ｩ|a|r|`|4|`|#|`|ｷ|`チ|O|8|8いったい、どうすればいいって言うんだ。|I|Z世界を救う方法は、おれ達が|C",
    }

    # script = Script(str(script_path))
    # for address, sentence in script.script.items():
    #     if "0x:" in sentence:
    #         continue
    #     source_array[address] = sentence
    #     dialogue_array[address] = sentence

    # Check address
    result_dict = dict()
    for address, src_sentence in dialogue_array.items():
        if "=" not in address:
            continue

        [code_hex_start, code_hex_end] = address.split("=")
        start_address = int(code_hex_start, 16)
        end_address = int(code_hex_end, 16)

        search_str = None
        skip = False
        for letter in src_sentence:
            if skip:
                skip = False
                continue
            if letter == "|":
                skip = True
                continue
            if letter in CHECK_LETTERS:
                search_str = letter
                break

        if search_str is None:
            print(src_sentence)

        s, e, sentence_new = backward_check(bin, start_address, end_address, font_table, search_str, consider_1byte)
        result_dict[f"{s:05X}={e:05X}"] = sentence_new

    # Final print
    for address, sentence in source_array.items():
        console.print(f'[grey50]    "{address}": "{sentence}"[/grey50]')
    for address, sentence in result_dict.items():
        print(f'    "{address}": "{sentence}",')

    # overwrite
    if overwrite:
        kor_script_path = script_dir / script_path.name.replace("_jpn.json", "_kor.json")

        # Read a source script
        jpn_script = Script(str(script_path))
        kor_script = Script(str(kor_script_path))

        for (address, sentece), (address_new, sentence_new) in zip(source_array.items(), result_dict.items()):
            jpn_script.replace_sentence(address, address_new, sentence_new)
            kor_script.replace_sentence(address, address_new, sentence_new)

        # Save
        jpn_script.save(script_path)
        kor_script.save(kor_script_path)


if __name__ == "__main__":
    main()
