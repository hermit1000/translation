"""Extract each FQ3-SD slot's unit names into Japanese and Korean drafts."""

import json
import unicodedata
from pathlib import Path


WORKSPACE_PATH = Path(r"C:\work_han\workspace13")
NAME_BLOCK = 0x480

SAVE_NAME_TRANSLATIONS = {
    "ランドルフ": "랜돌프", "ホーク": "호크", "ラッセル": "러셀",
    "ケーシー": "케이시", "スティーブンソン": "스티븐슨", "ジュード": "주드",
    "アーノルド": "아놀드", "シュール": "슈르", "フィリップ": "필립",
    "パリッシュ": "패리시", "チャールズ": "찰스", "ルター": "루터",
    "エミール": "에밀", "ケリー": "켈리", "ディオール": "디오르",
    "レンブラント": "렘브란트", "ルノアール": "르누아르", "シモン": "시몬",
    "ジャン": "장", "ハイアット": "하이앗", "フランソワ": "프랑수아",
    "カペリ": "카페리",
}


def encode_name(name: str, words: dict[str, str]) -> str:
    output = []
    size = 0
    padded = name + ("_" if len(name) % 2 else "")
    for index in range(0, len(padded), 2):
        pair = padded[index:index + 2]
        if pair in words and len(words[pair]) == 4:
            output.append("{" + pair + "}")
            size += 2
            continue
        for char in pair:
            if char == "_":
                continue
            if "|" + char in words:
                output.append("{|" + char + "}")
                size += 1
            else:
                output.append(char)
                size += 2
    if size > 10:
        raise ValueError(f"save name {name!r} needs {size} bytes")
    return "".join(output) + "|_" * (10 - size)


def main() -> None:
    script_dir = WORKSPACE_PATH / "script-pc98"
    original = (WORKSPACE_PATH / "jpn-pc98" / "HITOBUF.DAT").read_bytes()
    japanese = json.loads((script_dir / "HITOBUF.DAT_jpn.json").read_text(encoding="utf-8"))
    korean = json.loads((script_dir / "HITOBUF.DAT_kor.json").read_text(encoding="utf-8"))
    words = json.loads((script_dir / "custom_word.json").read_text(encoding="utf-8"))
    translations = {}
    for address, value in korean.items():
        start = int(address.split("=")[0], 16)
        translations.setdefault(original[start:start + 10], value)

    for slot in range(6):
        source = (WORKSPACE_PATH / "jpn-pc98" / f"FQ3-SD.{slot:02d}").read_bytes()
        documents = {"jpn": {}, "kor": {}}
        unresolved = 0
        for address, japanese_name in japanese.items():
            start, end = (int(part, 16) for part in address.split("="))
            raw = source[NAME_BLOCK + start:NAME_BLOCK + end + 1]
            key = f"{start + NAME_BLOCK:05X}={end + NAME_BLOCK:05X}"
            if raw == original[start:end + 1]:
                documents["jpn"][key] = japanese_name
                documents["kor"][key] = korean[address]
                continue
            decoded = "".join(
                "|␀" if byte == 0 else "|_" if byte == 0x20
                else "|" + bytes((byte,)).decode("cp932")
                for byte in raw
            )
            documents["jpn"][key] = decoded
            translation = translations.get(raw)
            if translation is None and raw.endswith(b"\x00"):
                zeros = len(raw) - len(raw.rstrip(b"\x00"))
                translation = translations.get(raw[:-zeros] + b" " * zeros)
                if translation is not None:
                    # The translated name may use more bytes than the Japanese
                    # name, so use NUL for all remaining field bytes.
                    padding = 0
                    while translation.endswith("|_"):
                        translation = translation[:-2]
                        padding += 1
                    translation += "|␀" * padding
            if translation is None:
                name = unicodedata.normalize("NFKC", raw.rstrip(b"\x00 ").decode("cp932"))
                if name in SAVE_NAME_TRANSLATIONS:
                    translation = encode_name(SAVE_NAME_TRANSLATIONS[name], words)
                    if raw.endswith(b"\x00"):
                        zeros = len(raw) - len(raw.rstrip(b"\x00"))
                        suffix = "|_" * zeros
                        if translation.endswith(suffix):
                            translation = translation[:-len(suffix)] + "|␀" * zeros
            if translation is None:
                unresolved += 1
            documents["kor"][key] = translation if translation is not None else decoded
        for language, document in documents.items():
            target = script_dir / f"FQ3-SD.{slot:02d}_{language}.json"
            target.write_text(json.dumps(document, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
            print(f"{target}: {len(document)} names")
        print(f"slot {slot:02d}: {unresolved} changed names need Korean review")


if __name__ == "__main__":
    main()
