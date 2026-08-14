import json
from pathlib import Path
from rich.console import Console
from module.content import Content

control_codes = [
    "|S|U|F|0|0|5",
    "|G|N",
    "|G|X",
    "|G",
    "|N",
    "|W",
    "|Y",
    "|␀",
    "␀",
]


def main():
    console = Console()
    ws_num = 1
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_dirs = [
        # base_dir / "script-dos",
        base_dir / "script-pc98",
    ]

    # Read a pair of scripts
    for script_dir in script_dirs:
        for file in script_dir.rglob("*.json"):  # Use rglob to search subdirectories
            if "_jpn.json" not in file.name:
                continue

            if "EVENT" not in file.name:
                continue

            doc = ""

            dst_path = file.parent / file.name.replace("_jpn.json", "_kor.json")
            if not dst_path.exists():
                continue
            file_tag = f"{file.parent.name}/{file.name}"
            console.print(file_tag)
            with open(dst_path, "r", encoding="utf-8") as f:
                dst = json.load(f)

            # check address
            for address, dst_sentence in dst.items():
                if "=" not in address or not isinstance(dst_sentence, str):
                    continue
                dst_sentence = Content.parse(dst_sentence).text
                # Remove control codes
                for control_code in control_codes:
                    dst_sentence = dst_sentence.replace(control_code, "")

                # Replace space
                dst_sentence = dst_sentence.replace("|_", "_")
                dst_sentence = dst_sentence.replace("_", " ")
                dst_sentence = dst_sentence.replace("|.", ". ")
                dst_sentence = dst_sentence.replace("|?", "? ")
                dst_sentence = dst_sentence.replace("|!", "! ")
                dst_sentence = dst_sentence.replace(",", ", ")

                doc += f"{dst_sentence}\n"

            if len(doc):
                sav_path = file.parent / file.name.replace("_jpn.json", "_kor.txt")
                with open(sav_path, "w", encoding="utf-8") as f:
                    f.write(doc)


if __name__ == "__main__":
    main()
