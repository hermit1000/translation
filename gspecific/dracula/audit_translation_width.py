#!/usr/bin/env python3
"""Find untranslated and likely over-wide Dracula MES translations."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(r"C:\work_han\workspace2\script-pc98\MES")
PREFIX_RE = re.compile(r"^(?:PUT|P|A|F|I2L)\s*[^\[\]［］]*")
SPEAKER_RE = re.compile(r"［([^］]+)］")
TRANSLATED_SPEAKER_RE = re.compile(r"^\[([^]]+)\]")
SPEAKER_MAP = {
    "フランチェスカ": "프란체스카", "侍女": "하녀", "ドラキュラ": "드라큘라",
    "男": "남자", "少女": "소녀", "老婆": "노파", "老人": "노인", "門番": "문지기",
    "女": "여자", "女の声": "여자의 목소리", "サンジェルマン": "생제르맹",
    "アリシア": "알리시아", "メイド": "하녀", "女の像": "여인상",
}


def text_len(value: str) -> int:
    return len(value.replace(" ", ""))


def main() -> int:
    empty = []
    overflow = []
    speaker_mismatches = []
    total = translated = 0
    for path in sorted(ROOT.glob("*_lang.json")):
        if path.name.upper() == "OP.MES_LANG.JSON":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for kind in ("dialogue_groups", "overlay_texts"):
            for entry in data.get(kind, []):
                total += 1
                translation = entry.get("translation", "")
                if not translation:
                    empty.append((path.name, kind, entry.get("offset"), entry.get("original", "")))
                    continue
                if translation == "@keep":
                    continue
                translated += 1
                original_speaker = SPEAKER_RE.search(entry.get("original", ""))
                translated_speaker = TRANSLATED_SPEAKER_RE.search(translation)
                if original_speaker and translated_speaker:
                    expected = SPEAKER_MAP.get(original_speaker.group(1), original_speaker.group(1))
                    if expected not in translated_speaker.group(1):
                        speaker_mismatches.append((path.name, entry.get("offset"), original_speaker.group(1), translated_speaker.group(1)))
                clean = translation
                translated_len = text_len(clean)
                original_len = text_len(entry.get("original", ""))
                if translated_len > 40 or (original_len and translated_len > original_len * 1.8):
                    overflow.append((translated_len, original_len, path.name, kind, entry.get("offset"), translation))
    print(f"total={total} translated={translated} empty={len(empty)}")
    print(f"overflow_candidates={len(overflow)}")
    print(f"speaker_mismatches={len(speaker_mismatches)}")
    for item in speaker_mismatches[:100]: print("SPEAKER_MISMATCH", *item)
    for item in sorted(overflow, reverse=True)[:100]: print("OVERFLOW", *item)
    for item in empty[:100]: print("EMPTY", *item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
