from pathlib import Path
from module.script import Script

MAIN_EXE_FILTER_START = 0x0
MAIN_EXE_FILTER_END = 0x050D1


def main():
    ws_num = 1
    platform = "pc98"
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_dir = base_dir / f"script-{platform}"

    for file in script_dir.rglob("*.json"):  # Use rglob to search subdirectories
        if "_jpn.json" not in file.name:
            continue

        if "SDATA.DAT" not in file.name:
            continue

        script = Script(str(file))

        list_to_delete = []
        list_to_update = []
        for address, content in script.script.items():
            start, end = address.split("=", maxsplit=1)
            start_address = int(start, 16)
            if not MAIN_EXE_FILTER_START <= start_address <= MAIN_EXE_FILTER_END:
                continue

            sentence = content.text
            if "0x:" in sentence:
                continue
            length = len(sentence)
            cnt_1byte = sentence.count("|")
            if length == cnt_1byte * 2:
                list_to_delete.append(address)
            elif sentence.startswith("|") and len(sentence) >= 2:
                new_address = f"{start_address + 1:0{len(start)}X}={end}"
                list_to_update.append((address, new_address, content))

        if len(list_to_delete):
            for address in list_to_delete:
                script.script.pop(address)

        if len(list_to_update):
            for address, new_address, content in list_to_update:
                script.script.pop(address)
                content.text = content.text[2:]
                script.script[new_address] = content

        if list_to_delete or list_to_update:
            script.save(file)


if __name__ == "__main__":
    main()
