import json
from pathlib import Path
from rich.console import Console
from module.content import Content
from module.font_table import get_cached_font_table


AUTO_FILL_REMAINING = False
FILL_CHARACTER = "␀"  # "_" or "␀"


def fill_remaining_space(dialogue: str, remaining_length: int, fill_character: str) -> str:
    if remaining_length <= 0:
        return dialogue
    if fill_character not in {"_", "␀"}:
        raise ValueError(f"Unsupported fill character: {fill_character}")

    dialogue += fill_character * (remaining_length // 2)
    if remaining_length % 2:
        dialogue += f"|{fill_character}"
    return dialogue


def main():
    ws_num = 5
    platform = "dos"
    platform = "pc98"
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    base_script_dir = base_dir / f"script-{platform}"
    script_path = base_script_dir / "MAIN.EXE_kor.json"

    # script_path = base_script_dir / "EVENT.EVT_kor.json"
    # script_path = base_script_dir / "MESSAGE.DAT_kor.json"
    # script_path = base_script_dir / "STR1.NB5_kor.json"

    custom_word_path = base_script_dir / "custom_word.json"
    custom_words = {}
    if custom_word_path.exists():
        with open(custom_word_path, "r", encoding="utf-8") as f:
            custom_words = json.load(f)

    dst_font_table = get_cached_font_table(
        file_path=Path("./font_table/font_table-kor-jin.json"),
        base_dir=base_dir,
        custom_char_path=base_script_dir / "custom_char.json",
    )

    # … ␀ ␁
    dialogue_array = {
        "48ED0=48F01": "가문의 영애와_ |␂귀하의 혼례를_|␂진행하려 합니다…",
        "48F04=48F35": "まことに恐悦至極|␂でござる！_謹ん|␂でお承けいたそう",
        "48F38=48F69": "女子で懐柔せんと|␂する腹か…_恥を|␂知れ、愚か者め！",
        "48F6C=48F9D": "良き縁でござる！|␂では早速、婚儀の|␂支度と参ろうか。",
        "48FA0=48FD1": "おとなしく一門と|␂なればよいものを|␂もはやこれまで！",
        "48FD4=49003": "こたびは御当家の|␂義心にすがりたく|␂参上した次第！",
    }

    console = Console()

    confirmed = False
    confirmed = True
    for script_range, dialogue in dialogue_array.items():
        dialogue = dialogue.replace(" ", "|_")
        # dialogue = dialogue.replace(" ", "_")

        dialogue_array[script_range] = dialogue
        length = dst_font_table.check_length_from_address(script_range)
        length_from_dialogue = dst_font_table.check_length_from_sentence(sentence=dialogue, custom_words=custom_words)
        if AUTO_FILL_REMAINING and length_from_dialogue < length:
            dialogue = fill_remaining_space(dialogue, length - length_from_dialogue, FILL_CHARACTER)
            dialogue_array[script_range] = dialogue
            length_from_dialogue = dst_font_table.check_length_from_sentence(
                sentence=dialogue,
                custom_words=custom_words,
            )

        if length != length_from_dialogue:
            confirmed = False
            console.print(
                f"{length} {dialogue} {length_from_dialogue - length}",
                style="yellow",
            )
        else:
            print(length, dialogue, length_from_dialogue - length)

    if confirmed:
        if not script_path.exists():
            print(f"Script file {script_path} does not exist.")
            return
        with open(script_path, "r", encoding="utf-8") as f:
            src_script = json.load(f)

        for script_range, dialogue in dialogue_array.items():
            if script_range in src_script:
                content = Content.parse(src_script[script_range])
                content.text = dialogue
            else:
                content = Content(text=dialogue)
            src_script[script_range] = content.serialize()

        console.print("Saved", style="green")
        with open(script_path, "w", encoding="utf-8", newline="\r\n") as f:
            json.dump(src_script, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
