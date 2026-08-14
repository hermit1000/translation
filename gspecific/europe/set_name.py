import json
from pathlib import Path
from module.script import Script


def main():
    ws_num = 3
    platform = "pc98"
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_base_dir = base_dir / f"script-{platform}"

    db_path = Path("./gspecific/europe/europe_name.json")
    with open(db_path, "r", encoding="utf-8") as f:
        name_db = json.load(f)

    for file in script_base_dir.glob("*.json"):  # Use rglob to search subdirectories
        if "_kor.json" not in file.name:
            continue

        # Check paths
        kor_script_path = file
        jpn_script_path = file.parent / file.name.replace("_kor.json", "_jpn.json")
        if not jpn_script_path.exists():
            print(f"{jpn_script_path.name} is not exists.")
            continue

        # Read source and destination script
        updated = False
        jpn_script = Script(str(jpn_script_path))
        kor_script = Script(str(kor_script_path))
        mod_list_jpn = []
        mod_list_kor = []

        for address, content in jpn_script.script.items():
            sentence = content.text
            start, end = address.split("=")
            start = int(start, 16)
            end = int(end, 16)
            jpn = ""
            kor = ""
            for v in name_db.values():
                if sentence in v["jpn_org"] and v["jpn_org"] == sentence:
                    jpn = v["jpn_org"]
                    kor = v["kor"]
                    break
            if len(kor) == 0:
                continue

            if len(kor) > 4:
                continue

            jpn_byte = len(jpn) // 2
            kor_byte = len(kor) * 2
            if jpn_byte >= kor_byte:
                kor += "|␀" * (jpn_byte - kor_byte)
                kor_script.script[address].text = kor
            else:
                jpn += "|␀" * (kor_byte - jpn_byte)
                end += kor_byte - jpn_byte
                mod_list_jpn.append([address, f"{start:05X}={end:05X}", jpn])
                mod_list_kor.append([address, f"{start:05X}={end:05X}", kor])
            updated = True
        if updated:
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
