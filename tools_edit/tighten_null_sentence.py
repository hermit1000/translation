from pathlib import Path
from module.script import Script


def main():
    # Tighten sentences (remove null) based on the source script

    ws_num = 3
    platform = "pc98"
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_base_dir = base_dir / f"script-{platform}"

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
        jpn_script = Script(str(jpn_script_path))
        kor_script = Script(str(kor_script_path))

        mod_list_jpn = []
        mod_list_kor = []
        for address, jpn_content in jpn_script.script.items():
            jpn_sentence = jpn_content.text
            start, end = address.split("=")
            start = int(start, 16)
            end = int(end, 16)

            if "␀" not in jpn_sentence:
                continue

            kor_sentence = kor_script.script[address].text

            # Check if there is 2-byte null character in the end of sentence
            if (not "|␀" == jpn_sentence[-2:]) and "␀" == jpn_sentence[-1]:
                if (not "|␀" == kor_sentence[-2:]) and "␀" == kor_sentence[-1]:
                    end -= 2
                    jpn_sentence_new = jpn_sentence[:-1]
                    kor_sentence_new = kor_sentence[:-1]
                    mod_list_jpn.append([address, f"{start:05X}={end:05X}", jpn_sentence_new])
                    mod_list_kor.append([address, f"{start:05X}={end:05X}", kor_sentence_new])

        for info in mod_list_jpn:
            address, address_new, jpn = info
            jpn_script.replace_sentence(address, address_new, jpn)
        for info in mod_list_kor:
            address, address_new, code = info
            kor_script.replace_sentence(address, address_new, code)

        print(len(mod_list_jpn))
        if len(mod_list_jpn):
            jpn_script.save(jpn_script_path)
            kor_script.save(kor_script_path)


if __name__ == "__main__":
    main()
