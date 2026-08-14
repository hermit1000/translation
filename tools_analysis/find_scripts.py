from pathlib import Path
from rich.console import Console
from module.script import Script


def main():
    console = Console()
    ws_num = 4
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_base_dir = base_dir

    script_base_dir = Path("c:/work_han/workspace{ws_num}/script-pc98")
    # script_base_dir = Path("c:/work_han/backup")

    find_source = True
    restriction = False

    sentence = "厳島"
    sentence_kor = "사콘"
    sentence_kor = sentence_kor.replace(" ", "_")

    # Read a pair of scripts
    for file in script_base_dir.rglob("*.json"):  # Use rglob to search subdirectories
        file_tag = f"{file.parent.name}/{file.name}"

        if "_jpn.json" not in file.name:
            continue

        dst_path = file.parent / file.name.replace("_jpn.json", "_kor.json")
        if not dst_path.exists():
            continue

        src_script = Script(str(file))
        dst_script = Script(str(dst_path))
        # console.print(file.name)

        if not find_source:
            for address, dst_content in dst_script.script.items():
                dst_sentence = dst_content.text
                found = False
                if restriction:
                    if sentence_kor == dst_sentence:
                        found = True
                else:
                    if sentence_kor in dst_sentence:
                        found = True
                if not found:
                    continue

                print("=============================")
                console.print(f"{address} {file_tag}", style="green")
                print(src_script.script[address].text)
                print(dst_sentence)
                print("=============================")
        else:
            for address, src_content in src_script.script.items():
                src_sentence = src_content.text
                found = False
                if restriction:
                    if sentence == src_sentence:
                        found = True
                else:
                    if sentence in src_sentence:
                        found = True
                if not found:
                    continue

                #     if not address in dst:
                #         print(f"Key error: {address} {file_tag}")
                #     buf_dst_sentence = dst[address]
                #     continue
                # if address in dst:
                #     dst_sentence = dst[address]
                #     if len(src_sentence) != len(dst_sentence):
                #         print(file.name, address)
                #         assert (
                #             0
                #         ), f"Sentence length is not matched. {len(src_sentence)} != {len(dst_sentence)}"
                #         continue

                print("=============================")
                console.print(f"{address} {file_tag}", style="green")
                print(src_sentence)
                print(dst_script.script[address].text)
                print("=============================")


if __name__ == "__main__":
    main()
