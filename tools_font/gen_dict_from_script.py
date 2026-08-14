import json
from pathlib import Path
from module.script import Script


def main():
    platform = "dos"
    platform = "pc98"

    work = "gen_dict"
    work = "update_sentence"

    ws_num = 0

    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_base_dir = base_dir / f"script-{platform}"

    # ===================================================================

    custom_word_path = script_base_dir / "custom_word.json"
    custom_words = {}
    if custom_word_path.exists():
        with open(custom_word_path, "r", encoding="utf-8") as f:
            custom_words = json.load(f)

    for file in script_base_dir.rglob("*.json"):  # Use rglob to search subdirectories
        if "_kor.json" not in file.name:
            continue

        print(file.name)
        # Read a script
        script = Script(str(file))

        for address, content in script.script.items():
            if not content.is_hex or content.description is None:
                continue

            code = content.hex_codes.strip()
            desc = content.description.strip()
            desc = desc.replace(" ", "_")

            if work == "gen_dict":
                if desc not in custom_words:
                    custom_words[desc] = code

            if work == "update_sentence":
                if desc in custom_words:
                    new_desc = f"{{{desc}}}"
                    # new_desc = new_desc.replace("|_", "_")
                    # new_desc = new_desc.replace("|␀", "")
                    content.text = new_desc

        if work == "update_sentence":
            script.save(file)

    if work == "gen_dict":
        custom_words = dict(sorted(custom_words.items()))
        with open(custom_word_path, "w", encoding="utf-8", newline="\r\n") as f:
            json.dump(custom_words, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
