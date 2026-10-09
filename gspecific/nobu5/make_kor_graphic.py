from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from gspecific.nobu5.decode_graphics import GRAPH_KEYPAD_HEIGHT, GRAPH_KEYPAD_PALETTE_8, GRAPH_KEYPAD_WIDTH
from module.font_image import return_img_roi
from module.font_table import FontTable


FONT_TABLE_PATH = Path("font_table/font_table-kor-jin.json")
BISCO_PATH = Path("c:/work_han/BISCO.bmp")
TITLE_FONT_PATH = Path("c:/work_han/font_ext/ext/ON 정속언해R.ttf")
PACK_DIR = Path("c:/work_han/workspace5/binary_inputs-pc98/PACK.NB5")
GRAPH_DIR = Path("c:/work_han/workspace5/binary_inputs-pc98/GRAPH.NB5")

FOREGROUND = (0, 0, 0)
SHADOW = (32, 69, 117)
OCHRE = (207, 154, 32)
YELLOW = (239, 207, 138)
WHITE = (255, 255, 255)

TITLE_PLACEMENTS = [
    ("전국 다이묘 현황", (23, 11, 249, 40), 32),
]
TITLE_SHADOW = True


@dataclass(frozen=True)
class TextPlacement:
    text: str
    x: int
    y: int
    shadow: bool = True
    underlay: bool = False
    foreground: tuple[int, int, int] = FOREGROUND
    underlay_color: tuple[int, int, int] = OCHRE
    underlay_offset: tuple[int, int] = (1, 1)
    highlight_color: tuple[int, int, int] | None = None
    highlight_offset: tuple[int, int] = (-1, 0)
    char_advance: int = 16


PLACEMENTS = {
    "01e600": [
        TextPlacement("년", 40, 16, False),
        TextPlacement("월", 72, 16, False),
        TextPlacement("일", 104, 16, False),
        TextPlacement("시", 136, 16, False),
        TextPlacement("병량", 272, 9, False),
        TextPlacement("병사", 360, 9, False),
    ],
    "01ec00": [
        TextPlacement("내정", 32, 5, False, True),
        TextPlacement("군사", 71, 5, False, True),
        TextPlacement("외교", 112, 5, False, True),
        TextPlacement("조략", 151, 5, False, True),
        TextPlacement("인사", 192, 5, False, True),
        TextPlacement("거래", 231, 5, False, True),
        TextPlacement("자국", 273, 5, False, True),
        TextPlacement("기능", 311, 5, False, True),
        TextPlacement("관망", 351, 5, False, True),
    ],
    "03ee00": [
        TextPlacement(
            "가보",
            25,
            122,
            False,
            True,
            FOREGROUND,
            OCHRE,
            (1, 1),
            WHITE,
            (0, -1),
            32,
        ),
        TextPlacement(
            "공주",
            25,
            142,
            False,
            True,
            FOREGROUND,
            OCHRE,
            (1, 1),
            WHITE,
            (0, -1),
            32,
        ),
        TextPlacement("전국무장열전", 14, 172, False, True, YELLOW, FOREGROUND),
    ],
}

TEXT_OVERRIDES = {
    "01ec00": ["내정", "군사", "외교", "조략", "인사", "거래", "자국", "기능", "관망"],
}

GRAPH_KEYPAD_PLACEMENTS = [
    TextPlacement(
        text,
        64,
        y,
        shadow=False,
        underlay=True,
        underlay_color=GRAPH_KEYPAD_PALETTE_8[6],
        underlay_offset=(1, 1),
        char_advance=20,
    )
    for text, y in (("중단", 22), ("취소", 42), ("최대", 62), ("결정", 82))
]


def resolve_windows_path(path: Path) -> Path:
    if path.exists():
        return path
    path_text = path.as_posix()
    if len(path_text) >= 3 and path_text[1:3] == ":/":
        drive = path_text[0].lower()
        resolved = Path("/mnt") / drive / path_text[3:]
        if resolved.exists() or resolved.parent.exists():
            return resolved
    return path


def load_text_entries(text_path: Path) -> dict[str, list[str]]:
    entries: dict[str, list[str]] = {}
    with open(text_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            stem, text = line.split(":", 1)
            entries[stem.strip()] = [part.strip() for part in text.split(",")]

    for stem, values in TEXT_OVERRIDES.items():
        entries[stem] = values
    return entries


def glyph_mask(font_img: Image.Image, font_table: FontTable, character: str) -> Image.Image:
    code = font_table.get_code(character)
    if code is None:
        raise ValueError(f"No font table code for character: {character}")

    y1, y2, x1, x2 = return_img_roi(code)
    glyph = font_img.crop((x1, y1, x2, y2)).convert("L")
    return glyph.point(lambda value: 255 if value == 0 else 0).convert("1")


def draw_character(
    canvas: Image.Image,
    mask: Image.Image,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
    ink = Image.new("RGB", mask.size, color)
    canvas.paste(ink, (x, y), mask)


def dither_mask(mask: Image.Image) -> Image.Image:
    sparse = Image.new("L", mask.size, 0)
    src = mask.load()
    dst = sparse.load()
    for y in range(mask.height):
        for x in range(mask.width):
            if src[x, y] and (x + y) % 2 == 0:
                dst[x, y] = 255
    return sparse


def draw_text(
    canvas: Image.Image,
    font_img: Image.Image,
    font_table: FontTable,
    placement: TextPlacement,
) -> None:
    for index, character in enumerate(placement.text):
        mask = glyph_mask(font_img, font_table, character)
        x = placement.x + index * placement.char_advance
        y = placement.y
        if placement.highlight_color is not None:
            dx, dy = placement.highlight_offset
            draw_character(canvas, mask, x + dx, y + dy, placement.highlight_color)
        if placement.shadow:
            draw_character(canvas, mask, x + 1, y + 1, SHADOW)
        if placement.underlay:
            dx, dy = placement.underlay_offset
            draw_character(canvas, mask, x + dx, y + dy, placement.underlay_color)
        draw_character(canvas, mask, x, y, placement.foreground)


def draw_title_text(
    canvas: Image.Image,
    font_path: Path,
    text: str,
    box: tuple[int, int, int, int],
    font_size: int | None = None,
) -> None:
    draw = ImageDraw.Draw(canvas)
    x1, y1, x2, y2 = box
    box_width = x2 - x1 + 1
    box_height = y2 - y1 + 1

    sizes = [font_size] if font_size is not None else range(34, 8, -1)
    selected = None
    for size in sizes:
        if size is None:
            continue
        font = ImageFont.truetype(font_path, size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_width = right - left
        text_height = bottom - top
        if font_size is not None or (text_width <= box_width and text_height <= box_height + 4):
            selected = (font, left, top, text_width, text_height)
            break
    if selected is None:
        raise ValueError(f"Could not fit title text: {text}")

    font, left, top, text_width, text_height = selected
    x = x1 + (box_width - text_width) // 2 - left
    y = y1 + (box_height - text_height) // 2 - top

    if TITLE_SHADOW:
        shadow_mask = Image.new("L", canvas.size, 0)
        shadow_draw = ImageDraw.Draw(shadow_mask)
        shadow_draw.text((x + 1, y + 1), text, font=font, fill=255)
        shadow_mask = shadow_mask.point(lambda value: 255 if value >= 96 else 0)
        shadow_mask = dither_mask(shadow_mask)
        canvas.paste(Image.new("RGB", canvas.size, SHADOW), (0, 0), shadow_mask)

    main_mask = Image.new("L", canvas.size, 0)
    main_draw = ImageDraw.Draw(main_mask)
    main_draw.text((x, y), text, font=font, fill=255)
    main_mask = main_mask.point(lambda value: 255 if value >= 96 else 0)
    canvas.paste(Image.new("RGB", canvas.size, FOREGROUND), (0, 0), main_mask)


def placements_from_text_file(pack_dir: Path) -> dict[str, list[TextPlacement]]:
    entries = load_text_entries(pack_dir / "text.txt")
    placements: dict[str, list[TextPlacement]] = {}
    for stem, base_placements in PLACEMENTS.items():
        words = entries.get(stem)
        if words is None:
            placements[stem] = base_placements
            continue
        if len(words) != len(base_placements):
            raise ValueError(f"{stem}: expected {len(base_placements)} labels, got {len(words)}")
        placements[stem] = [
            TextPlacement(
                word,
                placement.x,
                placement.y,
                placement.shadow,
                placement.underlay,
                placement.foreground,
                placement.underlay_color,
                placement.underlay_offset,
                placement.highlight_color,
                placement.highlight_offset,
                placement.char_advance,
            )
            for word, placement in zip(words, base_placements)
        ]
    return placements


def make_graph_keypad(graph_dir: Path, font_img: Image.Image, font_table: FontTable) -> Path:
    """Draw the four Korean keypad labels on the user-prepared background."""
    bg_path = graph_dir / "00585e.bg.png"
    canvas = Image.open(bg_path).convert("RGB")
    if canvas.size != (GRAPH_KEYPAD_WIDTH, GRAPH_KEYPAD_HEIGHT):
        raise ValueError(f"{bg_path}: expected {GRAPH_KEYPAD_WIDTH}x{GRAPH_KEYPAD_HEIGHT}, got {canvas.size}")
    for placement in GRAPH_KEYPAD_PLACEMENTS:
        draw_text(canvas, font_img, font_table, placement)
    out_path = graph_dir / "00585e.kor.png"
    canvas.save(out_path)
    print(f"Saved {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw Korean labels for Nobu5 PC-98 graphics.")
    parser.add_argument("--graph-only", action="store_true", help="only generate the GRAPH.NB5 keypad")
    args = parser.parse_args()
    pack_dir = resolve_windows_path(PACK_DIR)
    graph_dir = resolve_windows_path(GRAPH_DIR)
    font_path = resolve_windows_path(BISCO_PATH)
    title_font_path = resolve_windows_path(TITLE_FONT_PATH)

    font_table = FontTable(FONT_TABLE_PATH)
    font_img = Image.open(font_path).convert("1")

    make_graph_keypad(graph_dir, font_img, font_table)
    if args.graph_only:
        return

    title_canvas = Image.open(pack_dir / "016200.bg.png").convert("RGB")
    for text, box, font_size in TITLE_PLACEMENTS:
        draw_title_text(title_canvas, title_font_path, text, box, font_size)
    title_out_path = pack_dir / "016200.kor.png"
    title_canvas.save(title_out_path)
    print(f"Saved {title_out_path}")

    for stem, placements in placements_from_text_file(pack_dir).items():
        if stem == "016200":
            continue

        bg_path = pack_dir / f"{stem}.bg.png"
        if not bg_path.exists():
            raise FileNotFoundError(bg_path)

        canvas = Image.open(bg_path).convert("RGB")
        for placement in placements:
            draw_text(canvas, font_img, font_table, placement)

        out_path = pack_dir / f"{stem}.kor.png"
        canvas.save(out_path)
        print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
