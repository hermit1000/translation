from pathlib import Path
from module.script import Script


GIVEN_SENTENCES = ["|#"]


def main():
    ws_num = 1
    platform = "pc98"
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_dir = base_dir / f"script-{platform}"
    sentences_to_delete = set(GIVEN_SENTENCES)

    if not sentences_to_delete:
        print("GIVEN_SENTENCES is empty.")
        return

    for file in script_dir.rglob("*.json"):  # Use rglob to search subdirectories
        if "_jpn.json" not in file.name:
            continue

        if "SDATA.DAT" not in file.name:
            continue

        script = Script(str(file))
        list_to_delete = [
            address for address, content in script.script.items() if content.serialize() in sentences_to_delete
        ]

        if len(list_to_delete):
            for address in list_to_delete:
                script.script.pop(address)
            script.save(file)
            print(f"{file}: deleted {len(list_to_delete)} line(s).")


if __name__ == "__main__":
    main()
