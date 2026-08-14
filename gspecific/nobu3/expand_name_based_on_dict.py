import json
from pathlib import Path
from module.script import Script
from module.name_db import NameDB
from module.name_codec import split_pairs


def main():
    # To add 1byte space to the family name for isolating the given name
    # Only apply to the limited address range
    ws_num = 4
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_base_dir = base_dir / "script-pc98"
    bin_base_dir = base_dir / "jpn-pc98"

    game = f"nb{ws_num}"

    db = dict()
    if ws_num == 3:
        with open("C:/work_han/translation/name_db/nb3/region_db.json", "r", encoding="utf-8") as f:
            region_db = json.load(f)
        db |= region_db
    else:
        with open("C:/work_han/translation/name_db/region_db.json", "r", encoding="utf-8") as f:
            region_db = json.load(f)
        db = region_db

    name_db = NameDB()
    for japanese_name, korean_name, _ in name_db.iter_name_pairs(game):
        # given name
        db[japanese_name.given] = korean_name.given

        # family name
        if japanese_name.family == "北条":
            db[japanese_name.family] = "호조"
        else:
            db[japanese_name.family] = korean_name.family

    for file in script_base_dir.rglob("*.json"):  # Use rglob to search subdirectories
        print(file.name)
        if "_kor.json" not in file.name:
            continue

        # Check paths
        kor_script_path = file
        jpn_script_path = file.parent / file.name.replace("_kor.json", "_jpn.json")
        if not jpn_script_path.exists():
            print(f"{jpn_script_path.name} is not exists.")
            continue

        # Read source and destination script
        jpn_script = Script(str(jpn_script_path))
        kor_script = Script(str(kor_script_path))

        # Read the source binary data
        bin_data_path = bin_base_dir / str(file.relative_to(script_base_dir)).replace("_kor.json", "")

        if not Path(bin_data_path).exists():
            print(f"{bin_data_path} does not exist.")
            continue

        with open(bin_data_path, "rb") as f:
            bin_data = f.read()
        bin_data = bytearray(bin_data)

        mod_list_jpn = []
        mod_list_kor = []

        for address, jpn_content in jpn_script.script.items():
            jpn_sentence = jpn_content.text
            start, end = address.split("=")
            start = int(start, 16)
            end = int(end, 16)

            if address == "3EC6C=3EC6F":
                print(address)

            kor_sentence = kor_script.script[address].text

            # Check 1-byte null count
            jpn_byte_add = jpn_sentence.count("|␀")
            jpn_sentence_filtered = jpn_sentence.replace("|␀", "")
            jpn_byte_add += jpn_sentence_filtered.count("␀") * 2
            jpn_sentence_filtered = jpn_sentence_filtered.replace("␀", "")

            # Find new name from DB
            if jpn_sentence_filtered not in db:
                continue
            jpn_byte_filtered = len(jpn_sentence_filtered) * 2

            content = db[jpn_sentence_filtered]
            kor_sentence_new = ""
            pairs, _ = split_pairs(content)
            for pair in pairs:
                kor_sentence_new += f"{{{pair}}}"
            kor_byte = len(pairs) * 2

            diff = jpn_byte_filtered - kor_byte

            if diff == 0 and jpn_byte_add:
                base_pos = end - jpn_byte_add
                mod_list_jpn.append([address, f"{start:05X}={base_pos:05X}", jpn_sentence_filtered])
                mod_list_kor.append([address, f"{start:05X}={base_pos:05X}", kor_sentence_new])
            elif diff >= 0:
                if diff // 2:
                    kor_sentence_new += "␀" * (diff // 2)
                if diff % 2:
                    kor_sentence_new += "|␀"
                kor_script.script[address].text = kor_sentence_new

            elif diff < 0:
                # Need to check binary in jpn
                base_pos = end - jpn_byte_add
                search_space = bin_data[base_pos + 1 : base_pos - diff + 1]
                is_all_zero = all(b == 0 for b in search_space)

                if is_all_zero:
                    jpn_sentence_new = jpn_sentence_filtered
                    if (-diff) // 2:
                        jpn_sentence_new += "␀" * (-diff // 2)
                    if (-diff) % 2:
                        jpn_sentence_new += "|␀"
                    mod_list_jpn.append([address, f"{start:05X}={base_pos - diff:05X}", jpn_sentence_new])
                    mod_list_kor.append([address, f"{start:05X}={base_pos - diff:05X}", kor_sentence_new])
                else:
                    print(f"Address mismatch: {address},{jpn_sentence},{kor_sentence}")

        for info in mod_list_jpn:
            address, address_new, jpn = info
            jpn_script.replace_sentence(address, address_new, jpn)
        for info in mod_list_kor:
            address, address_new, code = info
            kor_script.replace_sentence(address, address_new, code)

        jpn_script.save(jpn_script_path)
        kor_script.save(kor_script_path)


if __name__ == "__main__":
    main()
