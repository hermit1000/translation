import json
from pathlib import Path
from rich.console import Console
from module.content import Content
from module.font_table import get_cached_font_table


def resolve_path(path: Path) -> Path:
    if path.exists():
        return path
    path_text = str(path)
    if len(path_text) >= 3 and path_text[1:3] == ":/":
        wsl_path = Path("/mnt") / path_text[0].lower() / path_text[3:]
        if wsl_path.exists() or wsl_path.parent.exists():
            return wsl_path
    return path


def load_custom_words(script_dir: Path, language: str) -> dict:
    custom_words = {}
    for file_name in (
        "custom_word.json",
        f"custom_word_{language}.json",
        f"custom_word_ext_{language}.json",
    ):
        custom_word_path = script_dir / file_name
        if not custom_word_path.exists():
            continue
        with open(custom_word_path, "r", encoding="utf-8") as f:
            custom_words.update(json.load(f))
    return custom_words


def main():
    console = Console()
    ws_num = 5
    base_dir = resolve_path(Path(f"c:/work_han/workspace{ws_num}"))
    script_dirs = [
        # base_dir / "script-dos",
        base_dir / "script-pc98",
    ]

    dictionary = dict()

    # Read an existing dictionary
    dictionary_path = base_dir / "dictionary.json"
    annoying_path = base_dir / "annoying.json"

    # Check num of key
    num_sentences = 0

    # Read a pair of scripts
    for script_dir in script_dirs:
        # Read a custom word dictionary
        src_custom_words = load_custom_words(script_dir, "jpn")
        dst_custom_words = load_custom_words(script_dir, "kor")

        for file in script_dir.rglob("*.json"):  # Use rglob to search subdirectories
            if "_jpn.json" not in file.name:
                continue
            if file.name.startswith("custom_word"):
                continue

            # if "MAIN" in file.name:
            #     continue

            dst_path = file.parent / file.name.replace("_jpn.json", "_kor.json")
            if not dst_path.exists():
                continue
            file_tag = f"{file.parent.name}/{file.name}"
            console.print(file_tag)
            with open(file, "r", encoding="utf-8") as f:
                src = json.load(f)
            with open(dst_path, "r", encoding="utf-8") as f:
                dst = json.load(f)

            src_font_table = get_cached_font_table(
                file_path=Path("./font_table/font_table-jpn.json"),
                base_dir=base_dir,
                custom_char_path=script_dir / "custom_char.json",
            )
            dst_font_table = get_cached_font_table(
                file_path=Path("./font_table/font_table-kor-jin.json"),
                base_dir=base_dir,
                custom_char_path=script_dir / "custom_char.json",
            )

            # Check sentences
            num_sentences += len(src.items())

            # Check address
            for address, src_sentence in src.items():
                if "=" not in address:
                    continue
                # Check if the address is in the destination script
                if address not in dst:
                    continue
                src_sentence = Content.parse(src_sentence).text

                # Check if the src and dst sentences are valid
                length = src_font_table.check_length_from_address(address)
                length_from_src_sentence = src_font_table.check_length_from_sentence(
                    sentence=src_sentence,
                    custom_words=src_custom_words,
                )

                if length != length_from_src_sentence:
                    console.print(f"{address} {file_tag}", style="red")
                    assert 0, f"Jpn sentence length is not matched. {address}:{length} != {length_from_src_sentence}"
                    continue

                # Check if the src and dst sentences are valid
                dst_sentence = Content.parse(dst[address]).text
                length_from_dst_sentence = dst_font_table.check_length_from_sentence(
                    sentence=dst_sentence,
                    custom_words=dst_custom_words,
                )
                if length != length_from_dst_sentence:
                    console.print(f"{address} {file_tag}", style="red")
                    assert 0, f"Kor sentence length is not matched. {address}:{length} != {length_from_dst_sentence}"
                    continue

                count_false_character, false_character = dst_font_table.verify_sentence(dst_sentence)
                # if count_false_character:
                #     console.print(f"{address} {file_tag}", style="red")
                #     continue

                # Check ignore sentences
                if len(dst_sentence.replace("@", "")) == 0:
                    continue

                # Add the sentence to the dictionary
                if src_sentence not in dictionary:
                    dictionary[src_sentence] = {
                        "count": 0,
                        "reference": 0,
                        "translated": [],
                    }

                dictionary[src_sentence]["reference"] += 1
                if dst_sentence not in dictionary[src_sentence]["translated"]:
                    dictionary[src_sentence]["count"] += 1
                    dictionary[src_sentence]["translated"].append(dst_sentence)

    print("Number of sentences = ", num_sentences)
    print("Number of sentence keys = ", len(dictionary.keys()))

    # Save a dictionary
    with open(dictionary_path, "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(dictionary, f, ensure_ascii=False, indent=4)
        f.write("\n")

    # Make an annoying dictionary - for cases that a source script has multiple destination scripts
    annoying = dict()
    for key, value in dictionary.items():
        if value["count"] > 1:
            annoying[key] = value

    print("Number of scripts = ", len(dictionary))
    print("Number of annoying scripts = ", len(annoying))

    # Save the annoying dictionary
    with open(annoying_path, "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(annoying, f, ensure_ascii=False, indent=4)
        f.write("\n")


if __name__ == "__main__":
    main()
