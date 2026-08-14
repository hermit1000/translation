import json
from pathlib import Path
from module.script import Script
from rich.console import Console
from module.name_db import NameDB


def main():
    ws_num = 4
    platform = "pc98"
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_base_dir = base_dir / f"script-{platform}"
    src_bin_base_dir = base_dir / f"jpn-{platform}"

    name_db = NameDB()
    with open("C:/work_han/translation/name_db/region_db.json", "r", encoding="utf-8") as f:
        region_db = json.load(f)
    with open("C:/work_han/translation/name_db/etc_db.json", "r", encoding="utf-8") as f:
        etc_db = json.load(f)

    code_db_path = Path("C:/work_han/font_update_db/code.json")
    with open(code_db_path, "r", encoding="utf-8") as f:
        code_db = json.load(f)

    console = Console()
    for file in script_base_dir.glob("*.json"):  # Use rglob to search subdirectories
        if "_kor.json" not in file.name:
            continue

        # Check paths
        kor_script_path = file
        jpn_script_path = file.parent / file.name.replace("_kor.json", "_jpn.json")
        if not jpn_script_path.exists():
            print(f"{jpn_script_path.name} is not exists.")
            continue

        # Check a source data path
        src_data_path = src_bin_base_dir / str(file.relative_to(script_base_dir)).replace("_kor.json", "")
        if not src_data_path.exists():
            print(f"{src_data_path.name} is not exists.")
            continue

        # Read source and destination script
        jpn_script = Script(str(jpn_script_path))
        kor_script = Script(str(kor_script_path))

        # Read the source binary data
        if not Path(src_data_path).exists():
            return
        with open(src_data_path, "rb") as f:
            data = f.read()
        data = bytearray(data)
        console.print(f"Data size: {src_data_path}({len(data):,} bytes)")

        mod_list_jpn = []
        mod_list_kor = []
        for address, content in jpn_script.script.items():
            sentence = content.text
            start, end = address.split("=")
            start = int(start, 16)
            end = int(end, 16)

            sentence_filtered = sentence.replace("|␀", "")
            sentence_filtered = sentence_filtered.replace("␀", "")

            kor = ""
            if sentence_filtered in name_db.given_name_db:
                kor = name_db.given_name_db[sentence_filtered]["kor"]
            if sentence_filtered in name_db.family_name_db:
                kor = name_db.family_name_db[sentence_filtered]["kor"]
            if sentence_filtered in region_db:
                kor = region_db[sentence_filtered]
            if sentence_filtered in etc_db:
                kor = etc_db[sentence_filtered]

            if len(kor) == 0:
                continue

            if isinstance(kor, list):
                continue

            if kor not in code_db:
                continue

            code = code_db[kor]
            code_len = len(code) // 4

            if len(sentence) == code_len:
                # kor_script.script[address] = f"0x:{code}# {kor}"
                kor_script.script[address].text = f"{{{kor}}}"
                continue

            if len(sentence) > code_len:
                continue

            # len(sentence) < code_len인 경우
            diff = code_len - len(sentence)
            if diff > 0:
                # Need to check binary
                blank = True
                for i in range(diff * 2 + 1):
                    if data[end + i + 1] != 0x00:
                        blank = False

                if not blank:
                    continue

                end += diff * 2
                jpn_sentence = sentence + "␀" * diff
                # kor_sentence = f"0x:{code}# {kor}"
                kor_sentence = f"{{{kor}}}"
                mod_list_jpn.append([address, f"{start:05X}={end:05X}", jpn_sentence])
                mod_list_kor.append([address, f"{start:05X}={end:05X}", kor_sentence])

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
