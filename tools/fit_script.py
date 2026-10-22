import json
from pathlib import Path
from rich.console import Console
from module.content import Content
from module.font_table import get_cached_font_table


AUTO_FILL_REMAINING = False
FILL_CHARACTER = "␀"  # "_" or "␀"
line_check = -1  # Debug output width; -1 disables line wrapping.


def format_debug_dialogue(dialogue: str, font_table, custom_words: dict) -> str:
    if line_check == -1:
        return dialogue
    if line_check <= 0:
        raise ValueError("line_check must be -1 or a positive integer")

    lines = []
    current_line = []
    current_length = 0
    index = 0
    while index < len(dialogue):
        if dialogue.startswith("|␂", index):
            lines.append("".join(current_line))
            current_line = []
            current_length = 0
            index += 2
            continue

        if dialogue[index] == "{" and "}" in dialogue[index:]:
            end = dialogue.index("}", index) + 1
            token = dialogue[index:end]
        elif dialogue[index] == "|" and index + 1 < len(dialogue):
            token = dialogue[index : index + 2]
        else:
            token = dialogue[index]

        token_length = font_table.check_length_from_sentence(token, custom_words=custom_words)
        if current_line and current_length + token_length > line_check:
            lines.append("".join(current_line))
            current_line = []
            current_length = 0

        current_line.append(token)
        current_length += token_length
        index += len(token)

    if current_line or not lines:
        lines.append("".join(current_line))
    return "\n".join(lines)


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
    script_path = base_script_dir / "BFILE.NB5_kor.json"

    # script_path = base_script_dir / "EVENT.EVT_kor.json"
    # script_path = base_script_dir / "MESSAGE.DAT_kor.json"

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
        # "01670=01702": "명문・오미 {|사}{|사}{|키}씨의 적류.남오미로 |␂力を伸ばし、三好氏に京を追われた足利|␂義晴・義輝を擁護して上洛、仲裁に奔走|␂する。織田信長に抵抗し、所領を失う。",
        "01714=01788": "義道の父。一色家は、室町幕府にて「四|␂職」の一つを務めた名家。丹後国の覇権|␂を巡って、若狭武田家との抗争に明け暮|␂れた。",
        "017B8=0184A": "{|石田三成に「過ぎたるもの」と謳われた|␂ほどの兵法者。知勇並ぶ者なく、三成は|␂彼を自分の禄の半分近くで召し抱えたと|␂いう。関ヶ原にて壮絶な最期を遂げた。",
    }

    # "01670=01702": "명문 오미 사사키씨의 적류. 미나미오미로 세력을|␂넓히고 미요시씨에게 교토에서 쫓겨난 아시카가|␂요시하루·요시테루를 보호해 상락하고 중재에 힘썼다.|␂오다 노부나가에 저항하다 영지를 잃었다.",
    # "01714=01788": "요시미치의 아버지. 잇시키가는 무로마치 막부에서 「시키|␂시키」의 하나를 맡은 명문가였다. 단고국의 패권을|␂둘러싸고 와카사 다케다가와의 항쟁에|␂평생을 보냈다.",
    # "017B8=0184A": "이시다 미쓰나리에게 「분에 넘치는 인재」라 칭송받을|␂정도의 병법가. 지혜와 용맹에서 견줄 자가 없어 미쓰나리는|␂자신의 녹봉 절반 가까이를 내어 그를 등용했다고|␂한다. 세키가하라에서 장렬한 최후를 맞았다.",

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
                f"{length} {format_debug_dialogue(dialogue, dst_font_table, custom_words)} {length_from_dialogue - length}",
                style="yellow",
            )
        else:
            print(
                length,
                format_debug_dialogue(dialogue, dst_font_table, custom_words),
                length_from_dialogue - length,
            )

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
