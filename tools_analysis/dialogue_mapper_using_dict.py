import json
from pathlib import Path
from rich.console import Console
from module.script import Script


def main():
    console = Console()

    platform = "dos"
    platform = "pc98"
    ws_num = 3
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    ref_base_dir = base_dir
    script_base_dir = base_dir / f"script-{platform}"

    # Read an existing dictionary
    dictionary_path = ref_base_dir / "dictionary.json"
    if not dictionary_path.exists():
        return
    with open(dictionary_path, "r", encoding="utf-8") as f:
        dictionary = json.load(f)

    # Read a pair of scripts
    for file in script_base_dir.rglob("*.json"):  # Use rglob to search subdirectories
        console.print(file.name)

        if "_jpn.json" not in file.name:
            continue
        dst_path = file.parent / file.name.replace("_jpn.json", "_kor.json")
        if not dst_path.exists():
            continue

        file_tag = f"{file.parent.name}/{file.name}"
        color = "green"

        src_script = Script(str(file))
        dst_script = Script(str(dst_path))

        # Check addresses in the source script
        modified = False
        for address, src_content in src_script.script.items():
            if "=" not in address:
                continue
            src_sentence = src_content.text

            if src_sentence not in dictionary:
                continue
            if address not in dst_script.script:
                continue

            translated = dictionary[src_sentence]["translated"]
            if len(translated) == 1:
                if dst_script.script[address].text != translated[0]:
                    dst_script.script[address].text = translated[0]
                    modified = True

                    console.print(f"{address},{file_tag}", style=color)
                    print(src_sentence)
                    print(translated[0])
            # else:
            #     print(len(translated))
            #     print(file.name, address)
            #     print(src_sentence)
            #     print(dst_sentence)

        if modified:
            print(dst_path)
            dst_script.save(str(dst_path))


if __name__ == "__main__":
    main()
