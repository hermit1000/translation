#!/usr/bin/env python3
"""Build manually configured Nobu2 Korean PNGs from *.bg.png images."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from module.pc98_image.palette import PC98_PALETTE_3BPP

PC98_COLORS = set(PC98_PALETTE_3BPP)


def title_text_mask(
    canvas_size: tuple[int, int],
    font: ImageFont.FreeTypeFont,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    text = "노부나가의 야망"
    font_size = 120
    letter_spacing = 5
    text_x = 80
    text_y = 15
    threshold = 112
    advances = [round(font.getlength(character)) for character in text]
    width = sum(advances) + letter_spacing * (len(text) - 1)
    temporary = Image.new("L", (width + 24, font_size + 40), 0)
    draw = ImageDraw.Draw(temporary)
    cursor = 12
    for character, advance in zip(text, advances):
        if character != " ":
            draw.text((cursor, 0), character, font=font, fill=255)
        cursor += advance + letter_spacing
    temporary = temporary.point(lambda value: 255 if value >= threshold else 0)
    content_box = temporary.getbbox()
    if content_box is None:
        raise ValueError("TITLE font produced no visible text")
    glyphs = temporary.crop(content_box)
    if (
        text_x + glyphs.width > canvas_size[0]
        or text_y + glyphs.height > canvas_size[1]
    ):
        raise ValueError("TITLE text does not fit its background")
    mask = Image.new("L", canvas_size, 0)
    mask.paste(glyphs, (text_x, text_y))
    return mask, (
        text_x,
        text_y,
        text_x + glyphs.width,
        text_y + glyphs.height,
    )


def make_title(background: Path, output: Path, fonts: Path) -> dict[str, object]:
    source = Image.open(background).convert("RGB")
    font = ImageFont.truetype(str(fonts / "행복고흥B.ttf"), 120)
    text_mask, text_box = title_text_mask(source.size, font)
    shadow_mask = Image.new("L", source.size, 0)
    shadow_mask.paste(text_mask, (3, 3))
    shadow_mask = shadow_mask.filter(ImageFilter.MaxFilter(3))
    result = source.copy()
    result.paste((0, 0, 0), mask=shadow_mask)
    result.paste((255, 255, 255), mask=text_mask)
    validate_pc98_colors(result, output)
    result.save(output)
    return {"text": "노부나가의 야망", "text_bbox": text_box}


def end2_glyph(
    character: str,
    font: ImageFont.FreeTypeFont,
) -> Image.Image:
    left, top, right, bottom = font.getbbox(character)
    antialiased = Image.new("L", (right - left + 4, bottom - top + 4), 0)
    draw = ImageDraw.Draw(antialiased)
    draw.text((2 - left, 2 - top), character, font=font, fill=255)
    content_box = antialiased.getbbox()
    if content_box is None:
        return Image.new("L", (1, 1), 0)
    glyph = antialiased.crop(content_box)
    glyph = glyph.resize(
        (
            max(1, round(glyph.width * 1.65)),
            max(1, round(glyph.height * 0.85)),
        ),
        Image.Resampling.BICUBIC,
    )
    return glyph.point(lambda value: 255 if value >= 112 else 0)


def end2_text_mask(
    canvas_size: tuple[int, int],
    font: ImageFont.FreeTypeFont,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    columns = (
        "인생오십",
        "세월은",
        "꿈과환상",
        "같구나",
        "태어나",
        "죽지않을",
        "이어디",
        "있으랴",
    )
    top_offsets = (0, 2, 1, 3, 0, 2, 1, 3)
    adjustments = {(1, 2): 12}
    left, right, top, row_pitch = 104, 556, 6, 24
    mask = Image.new("L", canvas_size, 0)
    column_step = (right - left) / (len(columns) - 1)
    for column_index, text in enumerate(columns):
        center_x = round(right - column_index * column_step)
        for row_index, character in enumerate(text):
            glyph = end2_glyph(character, font)
            x = center_x - glyph.width // 2
            y = (
                top
                + top_offsets[column_index]
                + row_index * row_pitch
                + adjustments.get((column_index, row_index), 0)
            )
            if (
                x < 0
                or y < 0
                or x + glyph.width > canvas_size[0]
                or y + glyph.height > canvas_size[1]
            ):
                raise ValueError(
                    f"END2 glyph {character!r} does not fit at ({x}, {y})"
                )
            mask.paste(glyph, (x, y), glyph)
    content_box = mask.getbbox()
    if content_box is None:
        raise ValueError("END2 font produced no visible text")
    return mask, content_box


def make_end2(background: Path, output: Path, fonts: Path) -> dict[str, object]:
    source = Image.open(background).convert("RGB")
    source = source.point(lambda value: 0 if value < 128 else 255)
    font = ImageFont.truetype(str(fonts / "행복고흥M.ttf"), 44)
    text_mask, text_box = end2_text_mask(source.size, font)
    result = source.copy()
    result.paste((255, 255, 255), mask=text_mask)
    validate_pc98_colors(result, output)
    result.save(output)
    return {"text_layout": "8 vertical columns", "text_bbox": text_box}


def validate_pc98_colors(image: Image.Image, output: Path) -> None:
    unknown = set(image.getdata()) - PC98_COLORS
    if unknown:
        preview = ", ".join(map(str, sorted(unknown)[:8]))
        raise ValueError(f"{output}: non-PC-98 colors: {preview}")


# Backgrounds and outputs both live under binary_inputs-pc98/<source file>/.
# Add new composites here explicitly. No folder is processed implicitly.
MANUAL_JOBS = (
    ("TITLE.PAK", "TITLE", make_title),
    ("END2.PAK", "END2", make_end2),
)


def build_all(workspace: Path) -> int:
    binary_inputs = workspace / "binary_inputs-pc98"
    fonts = workspace / "reverse/fonts"
    count = 0
    for directory_name, stem, routine in MANUAL_JOBS:
        directory = binary_inputs / directory_name
        background = directory / f"{stem}.bg.png"
        output = directory / f"{stem}.kor.png"
        if not background.is_file():
            raise FileNotFoundError(background)
        details = routine(background, output, fonts)
        count += 1
        print(f"{background} -> {output} ({details})")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("c:/work_han/workspace0"),
        help="workspace containing binary_inputs-pc98 and reverse/fonts",
    )
    args = parser.parse_args()
    count = build_all(args.workspace)
    print(f"generated {count} Korean PNG(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
