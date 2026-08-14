from pathlib import Path
from module.font_table import FontTable
from module.script import Script


def main():
    base_dir = Path("c:/work_han/workspace1")
    script_base_dir = base_dir / "script-pc98"
    src_bin_base_dir = base_dir / "kor-pc98"
    dst_bin_base_dir = base_dir / "kor-pc98-expand"
    dict_path = base_dir / "script-pc98-expand" / "modify.txt"
    # Read a font table
    font_table_path = "font_table/font_table-kor-jin.json"
    font_table = FontTable(font_table_path)

    # Read a dictionary
    dictionary = dict()
    with open(dict_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines:
            k, v = line.rstrip().split(",")
            if k not in dictionary:
                dictionary[k] = v
            else:
                assert 0, f"Duplicated key: {k}"

    for file in script_base_dir.rglob("*.json"):  # Use rglob to search subdirectories
        if "_kor.json" not in file.name:
            continue

        # Search for target sentences in the script
        src_script = Script(str(file))
        pairs = list()
        for address, content in src_script.script.items():
            sentence = content.text
            if sentence not in dictionary:
                continue
            pairs.append((address, sentence))

        if not pairs:
            continue

        pairs.sort(key=lambda p: int(p[0].split("=")[0], 16))

        # Read a binary data
        src_data_path = src_bin_base_dir / str(file.relative_to(script_base_dir)).replace("_kor.json", "")
        with open(src_data_path, "rb") as f:
            data = bytearray(f.read())

        # Expand the binary data
        offset = 0
        for address, sentence in pairs:
            start, end = address.split("=")
            start = int(start, 16)
            end = int(end, 16)

            current_start = start + offset
            original_len = end - start + 1

            # --- Verification Step ---
            original_data_from_bin = data[current_start : current_start + original_len]
            codes_hex_original = font_table.get_codes(sentence)
            expected_data_from_script = bytearray()
            try:
                for code in codes_hex_original:
                    expected_data_from_script.extend(bytes.fromhex(code))
            except TypeError:
                is_valid, bad_chars = font_table.verify_sentence(sentence)
                error_msg = f"Error: A character in the original sentence '{sentence}' at address {address} was not found in the font table. Invalid characters: {bad_chars}"
                raise ValueError(error_msg)

            if original_data_from_bin != expected_data_from_script:
                error_msg = f"""
Mismatch at address {address} in file {file.name}!
  Sentence: {sentence}
  Expected (from script): {expected_data_from_script.hex().upper()}
  Found (in binary)   : {original_data_from_bin.hex().upper()}"""
                raise ValueError(error_msg)
            # --- End Verification ---

            new_sentence = dictionary[sentence]
            codes_hex_new = font_table.get_codes(new_sentence)
            new_data = bytearray()
            try:
                for code in codes_hex_new:
                    new_data.extend(bytes.fromhex(code))
            except TypeError:
                is_valid, bad_chars = font_table.verify_sentence(new_sentence)
                error_msg = f"Error: A character in the new sentence '{new_sentence}' at address {address} was not found in the font table. Invalid characters: {bad_chars}"
                raise ValueError(error_msg)

            new_len = len(new_data)

            data[current_start : current_start + original_len] = new_data
            offset += new_len - original_len

        # Write the expanded binary data
        dst_data_path = dst_bin_base_dir / str(file.relative_to(script_base_dir)).replace("_kor.json", "")
        dst_data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dst_data_path, "wb") as f:
            f.write(data)


if __name__ == "__main__":
    main()
