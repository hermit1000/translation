from pathlib import Path
from module.script import Script


def main():
    ws_num = 1
    platform = "pc98"
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_dir = base_dir / f"script-{platform}"

    for file in script_dir.rglob("*.json"):  # Use rglob to search subdirectories
        if "_jpn.json" not in file.name:
            continue

        dst_path = file.parent / file.name.replace("_jpn.json", "_kor.json")
        if not dst_path.exists():
            continue

        jpn_script = Script(str(file))
        kor_script = Script(str(dst_path))

        list_to_delete = []
        for kor_address, kor_sentence in kor_script.script.items():
            if jpn_script.script.get(kor_address) is None:
                list_to_delete.append(kor_address)

        if len(list_to_delete):
            for address in list_to_delete:
                kor_script.script.pop(address)
            kor_script.save(dst_path)


if __name__ == "__main__":
    main()
