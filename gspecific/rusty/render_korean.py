#!/usr/bin/env python3
"""Render Korean opening captions with manually editable layout values."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"C:\work_han\workspace1")
INPUT_DIR = ROOT / "binary_inputs-pc98"
FONT_PATH = Path(r"C:\work_han\font_ext\ext\나눔\NanumGothic.ttf")
NAME_FONT_PATH = Path(r"C:\work_han\font_ext\ext\나눔\NanumBarunpenR.ttf")
FONT_SIZE = 28
STAFF_FONT_SIZE = 24
STAFF_NAME_FONT_SIZE = 24


@dataclass(frozen=True)
class CaptionLine:
    text: str
    center_x: int
    top_y: int


LAYOUTS = {
    "R_A23.MGX.png": [
        CaptionLine("수백 년 전으로 거슬러 올라가", 300, 2),
        CaptionLine("마수와 정령이 떠도는 칠흑 같은 밤의 이야기.", 307, 44),
        CaptionLine("그때 사람들은 밤을 몹시 싫어하고 두려워했다.", 300, 115),
    ],
    "R_A31.MGX.png": [
        CaptionLine("한때 이 트란실바니아 땅을 지배했던", 285, 2),
        CaptionLine("몬테카를로 후작이 한 인간의 힘에 의해", 281, 32),
        CaptionLine("봉인된 지 300년의 세월이 흘렀다.", 280, 62),
        CaptionLine("그 힘도 쇠퇴해 마수들이 깨어나기 시작했다.", 286, 102),
    ],
    "R_A36.MGX.png": [
        CaptionLine("언제부터인가 변방의 마을들에서", 278, 2),
        CaptionLine("아름다운 소녀들이 사라지는 사건이 잇따랐다.", 277, 32),
        CaptionLine("사라진 소녀들은 돌아오지 않고, 후작의 부활이", 276, 72),
        CaptionLine("변방의 마을들에 소문나기 시작했다.", 286, 102),
    ],
}
CANVAS_SIZES = {
    "R_A23.MGX.png": (610, 144),
    "R_A31.MGX.png": (576, 132),
    "R_A36.MGX.png": (560, 130),
}


@dataclass(frozen=True)
class StaffPart:
    text: str
    x: int
    top_y: int
    name: bool = False


STAFF_LAYOUTS = {
    "STAFF1.MGX.png": (368, 23, [StaffPart("원안·제작", 4, -4), StaffPart("아라이다 나오토", 218, -5, True)]),
    "STAFF2.MGX.png": (
        336,
        112,
        [
            StaffPart("캐릭터 원안", 1, 0),
            StaffPart("모리바야시 링고", 190, 0, True),
            StaffPart("디자인", 1, 58),
            StaffPart("나카무라 미츠히로", 180, 58, True),
            StaffPart("후루이치 켄지", 200, 84, True),
        ],
    ),
    "STAFF3.MGX.png": (
        336,
        102,
        [
            StaffPart("디자인 워크", 1, -2),
            StaffPart("니시야마 준이치", 195, -3, True),
            StaffPart("타카자와 고쿠로", 195, 23, True),
            StaffPart("오타 케이코", 215, 49, True),
            StaffPart("카토 도모코", 215, 75, True),
        ],
    ),
    "STAFF4.MGX.png": (
        288,
        112,
        [
            StaffPart("사운드", 0, -1),
            StaffPart("카지와라 마사히로", 130, -2, True),
            StaffPart("아라카와 케이치", 140, 24, True),
            StaffPart("타카미 류", 170, 50, True),
            StaffPart("진행", 0, 84),
            StaffPart("코노 가즈히로", 160, 84, True),
        ],
    ),
    "STAFF5.MGX.png": (
        368,
        50,
        [
            StaffPart("프로그램", 5, -3),
            StaffPart("아라이다 나오토", 230, -4, True),
            StaffPart("코조네 라이타", 240, 22, True),
        ],
    ),
    "STAFF6.MGX.png": (336, 24, [StaffPart("프로듀서", 1, -3), StaffPart("코야마 마사요시", 200, -4, True)]),
    "STAFF7.MGX.png": (216, 68, [StaffPart("제작·저작", 60, -3), StaffPart("주식회사 C-LAB", 25, 41)]),
}


def render(name: str, lines: list[CaptionLine]) -> Path:
    source = INPUT_DIR / name
    if name not in CANVAS_SIZES:
        raise KeyError(f"Missing canvas size: {name}")
    image = Image.new("1", CANVAS_SIZES[name], 0)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    for line in lines:
        box = draw.textbbox((0, 0), line.text, font=font)
        width = box[2] - box[0]
        x = round(line.center_x - width / 2 - box[0])
        draw.text((x, line.top_y - box[1]), line.text, font=font, fill=1)
    target = INPUT_DIR / name
    image.convert("RGB").save(target)
    print(f"OK {name} -> {target.name} ({FONT_SIZE}px)")
    return target


def render_staff(name: str, size: tuple[int, int], parts: list[StaffPart]) -> Path:
    image = Image.new("1", size, 0)
    draw = ImageDraw.Draw(image)
    label_font = ImageFont.truetype(FONT_PATH, STAFF_FONT_SIZE)
    name_font = ImageFont.truetype(NAME_FONT_PATH, STAFF_NAME_FONT_SIZE)
    for part in parts:
        font = name_font if part.name else label_font
        box = draw.textbbox((0, 0), part.text, font=font)
        draw.text((part.x - box[0], part.top_y - box[1]), part.text, font=font, fill=1)
    target = INPUT_DIR / name
    image.convert("RGB").save(target)
    print(f"OK {name} -> {target.name} (label {STAFF_FONT_SIZE}px, name {STAFF_NAME_FONT_SIZE}px)")
    return target


def main() -> None:
    for name, lines in LAYOUTS.items():
        render(name, lines)
    for name, (width, height, parts) in STAFF_LAYOUTS.items():
        render_staff(name, (width, height), parts)


if __name__ == "__main__":
    main()
