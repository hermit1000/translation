#!/usr/bin/env python3
"""Build manually configured Korean Nobu2 map graphics."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# DATA17.DAT_kor.json 0x01B04..0x01B94.
# Script addresses and token markers such as braces are intentionally omitted.
MAP17_LABELS = {
    1: "노토",
    2: "에치고·코즈케",
    3: "무사시·이즈",
    4: "카가·엣츄",
    5: "에치젠·와카사",
    6: "히다",
    7: "도토미·스루가",
    8: "미카와",
    9: "미노",
    10: "야마토",
    11: "오미",
    12: "이가",
    13: "이세·시마",
    14: "야마시로",
    15: "세츠·이즈미",
    16: "카이·시나노",
    17: "오와리",
}

# DATA50.DAT_kor.json 0x01B04..0x01CBD.
# Script addresses and token markers such as braces are intentionally omitted.
DATA50_LABELS = {
    1: "에조",
    2: "무츠",
    3: "리쿠츄·모리오카",
    4: "리쿠츄·이와사키",
    5: "우고",
    6: "릿젠",
    7: "우젠",
    8: "반성",
    9: "이와시로",
    10: "에치고·코즈케",
    11: "히타치",
    12: "시모츠케",
    13: "아와",
    14: "무사시·이즈",
    15: "카이·시나노",
    16: "노토",
    17: "엣츄",
    18: "히다",
    19: "키소·후쿠시마",
    20: "도토미·스루가",
    21: "카가",
    22: "에치젠",
    23: "미노",
    24: "미카와",
    25: "오와리",
    26: "이세·시마",
    27: "오미",
    28: "이가",
    29: "탄고·와카사",
    30: "탄바",
    31: "야마시로",
    32: "야마토",
    33: "세츠·이즈미",
    34: "키이",
    35: "이나바·타지마",
    36: "하리마",
    37: "이즈모·호우키",
    38: "산비",
    39: "아키·나가토",
    40: "사누키",
    41: "아와",
    42: "이요",
    43: "토사",
    44: "토사·나카무라",
    45: "부젠",
    46: "치쿠히",
    47: "분고",
    48: "히고",
    49: "휴가",
    50: "사츠마·오오스미",
}


def indexed_label(labels: dict[int, str], index: int) -> str:
    """Return the exact map caption form: decimal index followed by Korean."""
    return f"{index}{labels[index]}"


# Top-left positions copied from the original MAP17 label layout.
MAP17_POSITIONS = {
    1: (322, 0, 10, 14, 0, 0, False),
    2: (445, 63, 10, 14, 0, 1, False),
    3: (446, 111, 10, 14, 0, 1, False),
    4: (310, 17, 11, 14, 0, 2, False),
    5: (150, 34, 10, 14, 0, 2, False),
    6: (277, 47, 11, 14, 0, 1, False),
    7: (297, 130, 11, 14, 0, 2, False),
    8: (202, 131, 11, 14, 0, 1, False),
    9: (205, 67, 10, 14, 0, 1, False),
    10: (17, 127, 15, 14, 0, 1, False),
    11: (131, 71, 13, 14, 0, 0, False),
    12: (86, 111, 15, 14, 0, 1, False),
    13: (110, 129, 15, 14, 0, 4, False),
    14: (54, 79, 18, 14, 0, 0, False),
    15: (0, 82, 15, 10, 0, 0, True),
    16: (345, 75, 15, 14, 0, 1, False),
    17: (202, 99, 15, 14, 0, 1, False),
}

HOKURIKU_LABELS = {index: DATA50_LABELS[index] for index in (7, 9, 10, 12, 14, 15, 16, 17, 18, 19, 21, 22, 23)}

HOKURIKU_POSITIONS = {
    7: (474, 6, 9, 14, 1, 5, False),
    9: (429, 47, 9, 14, 1, 0, False),
    10: (311, 53, 14, 14, 1, 3, False),
    12: (399, 95, 12, 14, 1, 4, False),
    14: (340, 134, 16, 14, 2, 0, False),
    15: (231, 99, 15, 14, 0, 0, False),
    16: (137, 32, 13, 14, 2, 0, False),
    17: (158, 68, 13, 14, 0, 3, False),
    18: (118, 97, 13, 14, 1, 5, False),
    19: (167, 127, 15, 14, 0, 5, False),
    21: (83, 72, 15, 14, 0, 0, False),
    22: (32, 100, 16, 14, 1, 0, False),
    23: (46, 131, 16, 14, 1, 1, False),
}

KANTOU_LABELS = {index: DATA50_LABELS[index] for index in (8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 23, 24, 25)}

KANTOU_POSITIONS = {
    8: (430, 9, 9, 14, 1, 1, False),
    9: (336, 2, 9, 14, 1, 0, False),
    10: (242, 26, 14, 14, 1, 3, False),
    11: (392, 65, 12, 14, 1, 0, False),
    12: (338, 32, 12, 14, 1, 2, False),
    13: (358, 106, 13, 14, 1, 5, False),
    14: (282, 74, 16, 14, 2, 0, False),
    15: (172, 59, 15, 14, 0, 0, False),
    17: (95, 3, 13, 14, 0, 3, False),
    18: (73, 32, 13, 14, 1, 5, False),
    19: (119, 68, 15, 14, 0, 5, False),
    20: (118, 115, 16, 14, 1, 1, False),
    23: (25, 61, 16, 14, 1, 1, False),
    24: (48, 125, 16, 14, 1, 0, False),
    25: (29, 89, 16, 14, 0, 0, False),
}

KINKI_LABELS = {index: DATA50_LABELS[index] for index in (23, 25, 26, 27, 28, 30, 31, 32, 33, 34, 36, 40, 41)}

KINKI_POSITIONS = {
    23: (432, 26, 16, 14, 1, 1, False),
    25: (407, 54, 16, 14, 0, 0, False),
    26: (327, 92, 16, 14, 1, 0, False),
    27: (317, 18, 16, 14, 0, 0, False),
    28: (315, 59, 16, 14, 1, 0, False),
    30: (215, 20, 16, 14, 2, 0, False),
    31: (295, 29, 14, 10, 1, 1, False),
    32: (262, 86, 16, 11, 0, 1, True),
    33: (216, 53, 16, 14, 0, 0, False),
    34: (198, 122, 16, 14, 0, 0, False),
    36: (138, 23, 16, 14, 1, 0, False),
    40: (41, 68, 16, 14, 0, 3, False),
    41: (82, 106, 14, 14, 0, 1, False),
}

KYUSYU_LABELS = {index: DATA50_LABELS[index] for index in (39, 42, 43, 44, 45, 46, 47, 48, 49, 50)}

KYUSYU_POSITIONS = {
    39: (375, 5, 16, 14, 1, 1, False),
    42: (380, 64, 16, 14, 1, 2, False),
    43: (456, 64, 16, 14, 1, 2, False),
    44: (381, 96, 17, 14, 1, 2, False),
    45: (260, 13, 16, 14, 1, 2, False),
    46: (168, 23, 16, 14, 1, 0, False),
    47: (272, 50, 16, 14, 0, 2, False),
    48: (178, 62, 16, 14, 0, 0, False),
    49: (185, 103, 16, 14, 0, 1, False),
    50: (103, 126, 16, 14, 0, 1, False),
}

SHIKOKU_LABELS = {
    index: DATA50_LABELS[index] for index in (29, 30, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 47)
}

SHIKOKU_POSITIONS = {
    29: (415, 12, 16, 14, -63, -12, False),
    30: (435, 45, 16, 14, 2, 0, False),
    33: (437, 79, 16, 14, 0, 0, False),
    34: (407, 120, 16, 14, 1, 0, False),
    35: (336, 23, 16, 12, -40, 0, True),
    36: (351, 45, 16, 14, 1, 0, False),
    37: (232, 6, 16, 14, 0, 1, False),
    38: (224, 38, 16, 14, 1, 0, False),
    39: (111, 35, 16, 14, 1, 1, False),
    40: (272, 72, 16, 14, 0, 3, False),
    41: (302, 107, 14, 14, 0, 1, False),
    42: (135, 94, 16, 14, 1, 2, False),
    43: (201, 103, 16, 14, 1, 2, False),
    44: (146, 119, 17, 12, 1, 2, True),
    45: (9, 73, 16, 14, 1, 2, False),
    47: (18, 113, 16, 14, 0, 2, False),
}

TOUHOKU_LABELS = {index: DATA50_LABELS[index] for index in range(1, 13)}

TOUHOKU_POSITIONS = {
    1: (465, 1, 9, 14, 1, 0, False),
    2: (376, 43, 9, 14, 2, 0, False),
    3: (336, 86, 9, 14, 1, 1, False),
    4: (257, 91, 9, 14, 2, 0, False),
    5: (281, 43, 9, 14, 1, 0, False),
    6: (173, 111, 9, 14, 2, 1, False),
    7: (153, 68, 9, 14, 1, 5, False),
    8: (85, 124, 9, 14, 2, 1, False),
    9: (89, 95, 9, 14, 2, 0, False),
    10: (58, 54, 14, 14, 2, 0, False),
    11: (0, 133, 10, 14, 1, 0, False),
    12: (0, 103, 12, 14, 1, 0, False),
}

TYUBU_LABELS = {
    index: DATA50_LABELS[index]
    for index in (
        18,
        19,
        20,
        21,
        22,
        23,
        24,
        25,
        26,
        27,
        28,
        29,
        30,
        31,
        33,
        35,
        36,
    )
}

TYUBU_POSITIONS = {
    18: (391, 44, 13, 14, 0, 3, False),
    19: (451, 57, 13, 14, 1, 2, False),
    20: (432, 133, 16, 14, 2, 0, False),
    21: (317, 26, 15, 14, 0, 0, False),
    22: (278, 39, 16, 14, 0, 1, False),
    23: (324, 70, 16, 14, 0, 0, False),
    24: (375, 133, 16, 14, 0, 0, False),
    25: (342, 105, 15, 14, 2, 2, True),
    26: (297, 102, 16, 11, -10, 4, True),
    27: (243, 90, 16, 14, 0, 0, False),
    28: (245, 120, 16, 11, 0, 1, True),
    29: (132, 42, 15, 10, -26, -4, True),
    30: (143, 69, 16, 11, -11, 1, True),
    31: (199, 94, 13, 14, 0, 0, False),
    33: (145, 110, 16, 12, 1, 2, True),
    35: (7, 60, 16, 14, 0, 0, False),
    36: (57, 89, 16, 14, 1, 0, False),
}

LABEL_FONT_SIZE = 13
LABEL_LETTER_SPACING = 0
TEXT_COLOR = (255, 255, 0)
SHADOW_COLOR = (0, 0, 0)
MASK_THRESHOLD = 112
MAP_MASK_THRESHOLDS = {
    "MAP17.PAK": 160,
    "TYUBU.PAK": 160,
}
# Map backgrounds and label databases are assigned explicitly. Add each new
# layout here after its positions have been manually checked.
MANUAL_MAP_JOBS = {
    "MAP17.PAK": MAP17_LABELS,
    "TOUHOKU.PAK": TOUHOKU_LABELS,
    "HOKURIKU.PAK": HOKURIKU_LABELS,
    "KANTOU.PAK": KANTOU_LABELS,
    "TYUBU.PAK": TYUBU_LABELS,
    "KINKI.PAK": KINKI_LABELS,
    "SHIKOKU.PAK": SHIKOKU_LABELS,
    "KYUSYU.PAK": KYUSYU_LABELS,
}

RENDER_MAP_JOBS = {
    "MAP17.PAK": MAP17_POSITIONS,
    "HOKURIKU.PAK": HOKURIKU_POSITIONS,
    "KANTOU.PAK": KANTOU_POSITIONS,
    "KINKI.PAK": KINKI_POSITIONS,
    "KYUSYU.PAK": KYUSYU_POSITIONS,
    "SHIKOKU.PAK": SHIKOKU_POSITIONS,
    "TOUHOKU.PAK": TOUHOKU_POSITIONS,
    "TYUBU.PAK": TYUBU_POSITIONS,
}

MAP_LABEL_OVERRIDES = {
    "MAP17.PAK": {
        2: "에치고·\n      코즈케",
        3: "무사시·\n        이즈",
    },
    "KANTOU.PAK": {
        19: "키소\n후쿠시마",
    },
    "KYUSYU.PAK": {
        50: "사츠마·\n      오오스미",
    },
    "SHIKOKU.PAK": {
        33: "세츠·\n    이즈미",
    },
    "TOUHOKU.PAK": {
        4: "리쿠츄·\n      이와사키",
    },
    "TYUBU.PAK": {
        19: "키소·\n후쿠시마",
        20: "도토미·\n      스루가",
        29: "탄고·\n 와카사",
        31: "야마\n     시로",
    },
}


def glyph_mask(
    text: str,
    font: ImageFont.FreeTypeFont,
    mask_threshold: int = MASK_THRESHOLD,
) -> Image.Image:
    """Rasterize text as a hard-edged monochrome mask."""
    cursor = 0
    glyphs = []
    for character in text:
        left, top, right, bottom = font.getbbox(character)
        glyphs.append((character, cursor, left, top, right, bottom))
        cursor += round(font.getlength(character)) + LABEL_LETTER_SPACING
    left = min(cursor + glyph_left for _, cursor, glyph_left, *_ in glyphs)
    top = min(glyph_top for _, _, _, glyph_top, _, _ in glyphs)
    right = max(cursor + glyph_right for _, cursor, _, _, glyph_right, _ in glyphs)
    bottom = max(glyph_bottom for _, _, _, _, _, glyph_bottom in glyphs)
    antialiased = Image.new(
        "L",
        (right - left + 4, bottom - top + 4),
        0,
    )
    draw = ImageDraw.Draw(antialiased)
    for character, cursor, *_ in glyphs:
        draw.text(
            (cursor + 2 - left, 2 - top),
            character,
            font=font,
            fill=255,
        )
    antialiased = antialiased.point(lambda value: 255 if value >= mask_threshold else 0)
    content_box = antialiased.getbbox()
    if content_box is None:
        raise ValueError(f"font produced no visible text for {text!r}")
    return antialiased.crop(content_box)


def paste_caption(
    image: Image.Image,
    position: tuple[int, int, int, int, int, int, bool],
    index: int,
    label: str,
    label_font: ImageFont.FreeTypeFont,
    mask_threshold: int = MASK_THRESHOLD,
) -> None:
    """Draw a Korean label beside its separately copied original index."""
    (
        x,
        y,
        number_width,
        _,
        label_x_offset,
        label_y_offset,
        next_line,
    ) = position
    lines = []
    space_width = round(label_font.getlength(" "))
    for raw_line in label.splitlines():
        text = raw_line.lstrip(" ")
        leading_spaces = len(raw_line) - len(text)
        lines.append(
            (
                leading_spaces * space_width,
                glyph_mask(text, label_font, mask_threshold),
            )
        )
    if next_line:
        target_x = x + label_x_offset
        target_y = y + 10 + label_y_offset
    else:
        target_x = x + number_width + label_x_offset
        target_y = y + label_y_offset
    if target_x < 0 or target_y < 0:
        raise ValueError(f"caption {index} {label!r} has a negative position at ({target_x}, {target_y})")
    for line_x_offset, line in lines:
        line_x = target_x + line_x_offset
        image.paste(
            SHADOW_COLOR,
            (line_x + 1, target_y + 1),
            line,
        )
        image.paste(TEXT_COLOR, (line_x, target_y), line)
        target_y += line.height + 1


def copy_original_numbers(
    image: Image.Image,
    original: Image.Image,
    positions: Mapping[int, tuple[int, int, int, int, int, int, bool]],
) -> None:
    """Restore only the original PC-98 number rectangles."""
    if original.size != image.size:
        raise ValueError(f"original map size {original.size} != background size {image.size}")
    for _, (x, y, width, height, _, _, _) in positions.items():
        box = (x, y, x + width, y + height)
        image.paste(original.crop(box), (x, y))


def render_map(
    background: Path,
    original: Path,
    output: Path,
    labels: Mapping[int, str],
    positions: Mapping[int, tuple[int, int, int, int, int, int, bool]],
    font_path: Path,
    label_overrides: Mapping[int, str] | None = None,
    mask_threshold: int = MASK_THRESHOLD,
) -> None:
    source = Image.open(background).convert("RGB")
    original_image = Image.open(original).convert("RGB")
    label_font = ImageFont.truetype(str(font_path), LABEL_FONT_SIZE)
    if labels.keys() != positions.keys():
        raise ValueError(f"{background}: label and position indices do not match")
    copy_original_numbers(source, original_image, positions)
    label_overrides = label_overrides or {}
    for index, label in labels.items():
        paste_caption(
            source,
            positions[index],
            index,
            label_overrides.get(index, label),
            label_font,
            mask_threshold,
        )
    source.save(output)


def build_all(workspace: Path) -> int:
    map_dir = workspace / "binary_inputs-pc98/MAP"
    font_candidates = (
        workspace / "reverse/fonts/Maplestory Light.ttf",
        workspace.parent / "font_ext/ext/Maplestory Light.ttf",
    )
    font_path = next((path for path in font_candidates if path.is_file()), None)
    if font_path is None:
        raise FileNotFoundError(font_candidates[0])

    count = 0
    for source_name, positions in RENDER_MAP_JOBS.items():
        background = map_dir / f"{source_name}.BG.png"
        original = workspace / "image-pc98/MAP" / f"{Path(source_name).stem}.jpn.png"
        output = map_dir / f"{source_name}.KOR.png"
        if not background.is_file():
            raise FileNotFoundError(background)
        if not original.is_file():
            raise FileNotFoundError(original)
        render_map(
            background,
            original,
            output,
            MANUAL_MAP_JOBS[source_name],
            positions,
            font_path,
            MAP_LABEL_OVERRIDES.get(source_name),
            MAP_MASK_THRESHOLDS.get(source_name, MASK_THRESHOLD),
        )
        print(f"{background} -> {output} (Maplestory Light)")
        count += 1
    return count


def validate_label_databases() -> None:
    if tuple(MAP17_LABELS) != tuple(range(1, 18)):
        raise ValueError("MAP17_LABELS must contain consecutive indices 1..17")
    if tuple(DATA50_LABELS) != tuple(range(1, 51)):
        raise ValueError("DATA50_LABELS must contain consecutive indices 1..50")
    for database in (MAP17_LABELS, DATA50_LABELS):
        if any(not text or any(marker in text for marker in "{}|") for text in database.values()):
            raise ValueError("map labels must contain Korean display text only")


validate_label_databases()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("c:/work_han/workspace"),
        help="workspace containing binary_inputs-pc98/MAP and reverse/fonts",
    )
    args = parser.parse_args()
    count = build_all(args.workspace)
    print(f"generated {count} Korean map PNG(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
