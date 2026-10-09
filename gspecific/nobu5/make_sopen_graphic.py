"""Render SOPEN Korean text using BISCO or TrueType fonts and native palette colors."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from gspecific.nobu5.make_kor_graphic import BISCO_PATH, FONT_TABLE_PATH, glyph_mask
from module.font_table import FontTable


DEFAULT_DIR = Path("C:/work_han/workspace5/binary_inputs-pc98/SOPEN.NB5")
TITLE_INK_HEIGHT = 21
TITLE_STROKE_BOOST = 0.25
TITLE_DIGIT_TRACKING = -3
TITLE_TRACKING_OVERRIDES = {"군웅할거편": 2.0, "평안낙토편": 2.0, "야망전생편": 3.0}
TITLE_BACKGROUND_TOUCHUPS = {
    "00c579": [(148, 2), (208, 2), (209, 3), (256, 3), (57, 4), (260, 4), (39, 5)],
}


def ttf_mask(text, font_path, size, dimensions, supersample=False):
    scale = 4 if supersample else 1
    font = ImageFont.truetype(str(font_path), size * scale)
    left, top, right, bottom = font.getbbox(text)
    width, height = (value * scale for value in dimensions)
    mask = Image.new("L", (width, height))
    ImageDraw.Draw(mask).text(((width - (right - left)) // 2 - left,
                              (height - (bottom - top)) // 2 - top),
                             text, font=font, fill=255)
    if scale != 1:
        mask = mask.resize(dimensions, Image.Resampling.LANCZOS)
    return mask


def paste_ttf_mask(canvas, mask, position, graded, title_edge="warm"):
    if not graded:
        canvas.paste(0, position, mask.point(lambda value: 255 if value >= 128 else 0))
        return
    # Mask values measure ink coverage, not image brightness. Low coverage leaves
    # the original background intact. Every output value is an existing palette index.
    light = 6 if canvas.height == 28 else 7
    dark = 4
    if canvas.height == 28 and title_edge == "teal":
        light, dark = 9, 2
    levels = ((32, 96, light), (96, 176, dark), (176, 256, 0))
    if canvas.height == 28 and title_edge == "soft-teal":
        levels = ((48, 112, 6), (112, 176, 2), (176, 256, 0))
    if canvas.height == 28 and title_edge == "soft-warm":
        levels = ((48, 112, 6), (112, 176, 4), (176, 256, 0))
    for lower, upper, color in levels:
        selection = mask.point(lambda value: 255 if lower <= value < upper else 0)
        canvas.paste(color, position, selection)


def original_title_boxes(source):
    """Locate the two Japanese ink groups, ignoring the colored outer border."""
    columns = [x for x in range(1, source.width - 1)
               if any(source.getpixel((x, y)) == 0 for y in range(1, source.height - 1))]
    if not columns:
        raise ValueError("No Japanese title ink found")
    left_end, right_start = max(zip(columns, columns[1:]), key=lambda pair: pair[1] - pair[0])
    if right_start - left_end < 10:
        raise ValueError("Cannot locate the gap between the Japanese year and title")
    return [(columns[0], left_end + 1), (right_start, columns[-1] + 1)]


def title_part_mask(text, font_path, tracking=0):
    """Render spaced Hangul at 4x resolution, then resize as grayscale."""
    font = ImageFont.truetype(str(font_path), 28 * 4)
    left, top, right, bottom = font.getbbox(text)
    ink_height = bottom - top
    track = tracking * ink_height / TITLE_INK_HEIGHT
    pairs = ["가" <= a <= "힣" and "가" <= b <= "힣" for a, b in zip(text, text[1:])]
    digit_pairs = ["０" <= a <= "９" and "０" <= b <= "９" for a, b in zip(text, text[1:])]
    digit_track = TITLE_DIGIT_TRACKING * ink_height / TITLE_INK_HEIGHT
    width = math.ceil(right - left + sum(pairs) * track + sum(digit_pairs) * digit_track)
    mask = Image.new("L", (width, ink_height))
    draw = ImageDraw.Draw(mask)
    x = -left
    for index, character in enumerate(text):
        draw.text((x, -top), character, font=font, fill=255)
        x += font.getlength(character)
        if index < len(pairs) and pairs[index]:
            x += track
        if index < len(digit_pairs) and digit_pairs[index]:
            x += digit_track
    target_width = round(mask.width * TITLE_INK_HEIGHT / mask.height)
    return mask.resize((target_width, TITLE_INK_HEIGHT), Image.Resampling.LANCZOS)


def paste_title(canvas, text, font_path, graded, title_edge, source):
    year, separator, title = text.partition("년")
    if not separator:
        raise ValueError(f"Expected a year and title: {text}")
    # Use the font's fullwidth numeral glyphs and em-sized advances in the year.
    fullwidth_digits = str.maketrans("0123456789", "０１２３４５６７８９")
    parts = [(year + separator).translate(fullwidth_digits), title.strip()]
    boxes = original_title_boxes(source)
    masks = []
    positions = []
    for part, (left, right) in zip(parts, boxes):
        mask = title_part_mask(part, font_path)
        width = right - left
        pairs = sum("가" <= a <= "힣" and "가" <= b <= "힣" for a, b in zip(part, part[1:]))
        if pairs and width > mask.width:
            tracking = min(1.0, (width - mask.width) / pairs)
            mask = title_part_mask(part, font_path, tracking)
        if part in TITLE_TRACKING_OVERRIDES:
            mask = title_part_mask(part, font_path, TITLE_TRACKING_OVERRIDES[part])
        # Measure visible ink after stroke enhancement, excluding font side bearings.
        mask = Image.blend(mask, mask.filter(ImageFilter.MaxFilter(3)), TITLE_STROKE_BOOST)
        cutoff = 48 if graded and title_edge in ("soft-warm", "soft-teal") else 32 if graded else 128
        ink_box = mask.point(lambda value: 255 if value >= cutoff else 0).getbbox()
        if ink_box:
            mask = mask.crop((ink_box[0], 0, ink_box[2], mask.height))
        # Preserve glyph proportions even when Korean text exceeds its Japanese group.
        if mask.width > canvas.width - 12:
            raise ValueError(f"Title group is wider than the canvas: {part}")
        x = max(6, min(left + (width - mask.width) // 2, canvas.width - 6 - mask.width))
        masks.append(mask)
        positions.append(x)
    if positions[1] - positions[0] - masks[0].width < 12:
        total = masks[0].width + masks[1].width + 12
        if total > canvas.width - 12:
            raise ValueError(f"Title groups cannot fit without horizontal compression: {text}")
        positions[0] = (canvas.width - total) // 2
        positions[1] = positions[0] + masks[0].width + 12
    # Highest priority: balance the two outside margins of the complete ink group.
    span = positions[1] + masks[1].width - positions[0]
    shift = (canvas.width - span) // 2 - positions[0]
    positions = [x + shift for x in positions]
    for mask, x in zip(masks, positions):
        paste_ttf_mask(canvas, mask, (x, (canvas.height - TITLE_INK_HEIGHT) // 2), graded, title_edge)


def horizontal_mask(text, font_image, font_table):
    widths = [4 if char == " " else 8 if char.isascii() and not char.isdigit() else 16 for char in text]
    mask = Image.new("1", (sum(widths), 16))
    x = 0
    for char, width in zip(text, widths):
        if char != " ":
            glyph = glyph_mask(font_image, font_table, char)
            if width != glyph.width:
                # Only punctuation is narrow; digits retain their native 16px cells.
                box = glyph.getbbox()
                glyph = glyph.crop(box) if box else glyph
                glyph.thumbnail((width, 16), Image.Resampling.NEAREST)
            mask.paste(glyph, (x, (16 - glyph.height) // 2))
        x += width
    return mask


def paste_horizontal(canvas, text, box, font_image, font_table, graded=False):
    if font_table is None:
        x, y, width, height = box
        for size in range(height + 2, 7, -1):
            font = ImageFont.truetype(str(font_image), size)
            left, top, right, bottom = font.getbbox(text)
            if right - left <= width and bottom - top <= height:
                mask = ttf_mask(text, font_image, size, (width, height), graded)
                paste_ttf_mask(canvas, mask, (x, y), graded)
                return
        raise ValueError(f"Text does not fit: {text}")
    mask = horizontal_mask(text, font_image, font_table)
    x, y, width, height = box
    mask = mask.resize((min(width, round(mask.width * height / 16)), height), Image.Resampling.NEAREST)
    canvas.paste(0, (x + (width - mask.width) // 2, y), mask)


def paste_vertical(canvas, text, x, top, height, font_image, font_table, graded=False):
    text = text.replace(" ", "")
    advance = min(16, height // len(text))
    if advance < 12:
        raise ValueError(f"Vertical column too long: {text}")
    for index, char in enumerate(text):
        if font_table is None:
            if char == "・":
                dot_y = top + index * advance + advance // 2 - 1
                canvas.paste(0, (x + 7, dot_y, x + 9, dot_y + 2))
                continue
            mask = ttf_mask(char, font_image, advance, (16, advance), graded)
            paste_ttf_mask(canvas, mask, (x, top + index * advance), graded)
            continue
        mask = glyph_mask(font_image, font_table, char)
        mask = mask.resize((advance, advance), Image.Resampling.NEAREST)
        canvas.paste(0, (x + (16 - advance) // 2, top + index * advance), mask)


def background(source):
    canvas = source.copy()
    if source.height == 28:
        # Preserve the orange border and reconstruct the speckled title background
        # from its clean top rows. Remove black, blue and green Japanese glyphs.
        for y in range(1, source.height - 1):
            for x in range(1, source.width - 1):
                if source.getpixel((x, y)) in (0, 9, 12):
                    clean = source.getpixel((x, 1 + y % 3))
                    canvas.putpixel((x, y), clean if clean in (14, 15) else 14)
    else:
        canvas.paste(15, (0, 0, source.width, source.height))
    return canvas


def vertical_columns(text):
    if "\n" in text:
        return text.splitlines()
    if all(char.isdigit() or char == "・" for char in text):
        return [text]
    if "・" in text:
        return [part for part in text.split("・") if part]
    if " 지지 세력" in text:
        return [text.removesuffix(" 지지 세력"), "지지 세력"]
    return [text]


def draw_native_white(canvas, entry, font_image, font_table, source):
    """Place unchanged 16x16 BISCO glyphs; wrap text instead of rescaling it."""
    width, height = canvas.size
    if entry["direction"] == "horizontal":
        name, troops = entry["kor"].splitlines()
        name_width = sum(8 if character == " " else 16 for character in name)
        name_rows = [name] if name_width <= width else name.split()
        rows = name_rows + [troops.replace(" ", "")]
        if len(rows) * 16 > height:
            raise ValueError(f"Too many native font rows: {entry['kor']}")
        top = (height - len(rows) * 16) // 2
        for row, text in enumerate(rows):
            if row == len(rows) - 1:
                row_top = top + row * 16
                # Copy the whole original row, then remove the complete first glyph.
                # 兵 extends beyond x=16, and shorter counts shift its starting position.
                columns = [x for x in range(width)
                           if any(source.getpixel((x, y)) == 0 for y in range(24, 40))]
                left = columns[0]
                right = left
                while right in columns:
                    right += 1
                ink_top = min(y for y in range(24, 40)
                              if any(source.getpixel((x, y)) == 0 for x in range(left, right)))
                canvas.paste(source.crop((0, 24, width, 40)), (0, row_top))
                canvas.paste(15, (left, row_top, right, row_top + 16))
                mask = glyph_mask(font_image, font_table, "병")
                glyph_left, glyph_top, _, _ = mask.getbbox()
                canvas.paste(0, (left - glyph_left, row_top + ink_top - 24 - glyph_top), mask)
                continue
            text_width = sum(8 if character == " " else 16 for character in text)
            if text_width > width:
                raise ValueError(f"Native horizontal text is too long: {text}")
            x = (width - text_width) // 2
            for character in text:
                if character == " ":
                    x += 8
                    continue
                canvas.paste(0, (x, top + row * 16),
                             glyph_mask(font_image, font_table, character))
                x += 16
        return
    if entry.get("layout") == "single_column":
        text = entry["kor"].replace(" ", "")
        extent = sum(8 if character == "・" else 16 for character in text)
        if extent > height:
            raise ValueError(f"Native single column is too tall: {text}")
        x = (width - 16) // 2
        y = (height - extent) // 2
        for character in text:
            if character == "・":
                canvas.paste(0, (x + 7, y + 3, x + 9, y + 5))
                y += 8
            else:
                canvas.paste(0, (x, y), glyph_mask(font_image, font_table, character))
                y += 16
        return
    columns = vertical_columns(entry["kor"])
    if len(columns) > 2 or len(columns) * 16 > width:
        raise ValueError(f"Too many native font columns: {entry['kor']}")
    left = (width - len(columns) * 16) // 2
    for column, raw_text in enumerate(columns):
        is_person = ("\n" in entry["kor"] and column == 1) or (" 지지 세력" in entry["kor"] and column == 0)
        words = raw_text.split() if is_person else [raw_text.replace(" ", "")]
        text = "".join(words)
        break_after = {sum(len(word) for word in words[:index + 1]) - 1 for index in range(len(words) - 1)}
        group_space = 8 * len(break_after)
        x = left + (len(columns) - column - 1) * 16
        preferred_advance = 14 if is_person else 16
        advance = 16 if len(text) == 1 else min(preferred_advance, (height - 16 - group_space) // (len(text) - 1))
        masks = [None if character == "・" else glyph_mask(font_image, font_table, character)
                 for character in text]
        # Cell margins may overlap for long names, but visible glyph strokes may not.
        if any(mask is not None and mask.getbbox()[3] - mask.getbbox()[1] > advance for mask in masks):
            raise ValueError(f"Native vertical glyphs would overlap: {text}")
        extent = 16 + (len(text) - 1) * advance + group_space
        top = 0 if column == 0 else height - extent
        y = top
        for row, character in enumerate(text):
            if character == "・":
                canvas.paste(0, (x + 7, y + 7, x + 9, y + 9))
            else:
                canvas.paste(0, (x, y), masks[row])
            y += advance + (8 if row in break_after else 0)


def make_sopen(directory, font_path=None, graded=False, titles_only=False, title_edge="warm", white_native=False):
    if white_native and (font_path is not None or titles_only or graded):
        raise ValueError("Use --white-native by itself to preserve the finished yellow titles")
    if graded and font_path is None:
        raise ValueError("Graded grayscale rendering requires a TrueType font")
    entries = json.loads((directory / "text.json").read_text("utf-8"))
    font_table = FontTable(FONT_TABLE_PATH) if font_path is None else None
    font_image = Image.open(BISCO_PATH).convert("1") if font_path is None else font_path
    generated = []
    for filename, entry in entries.items():
        source_path = directory / filename
        if not source_path.exists():
            continue
        source = Image.open(source_path)
        if titles_only and source.height != 28:
            continue
        if white_native and source.height == 28:
            continue
        if source.mode != "P":
            raise ValueError(f"Expected an indexed source: {filename}")
        canvas = background(source)
        stem = filename.removesuffix(".jpn.png")
        # Seven tiny background speckles are omitted so the final title fits its
        # fixed compressed record. Draw text afterwards to preserve every glyph.
        for position in TITLE_BACKGROUND_TOUCHUPS.get(stem, []):
            canvas.putpixel(position, 14)
        canvas.save(directory / f"{stem}.bg.png")
        text = entry["kor"]
        width, height = canvas.size
        if white_native:
            draw_native_white(canvas, entry, font_image, font_table, source)
        elif height == 28:
            if font_table is None:
                paste_title(canvas, text, font_image, graded, title_edge, source)
            else:
                paste_horizontal(canvas, text, (6, 4, width - 12, 20), font_image, font_table, graded)
        elif entry["direction"] == "horizontal":
            for row, line in enumerate(text.splitlines()):
                if font_table is not None and line.startswith("병 ") and line[2:].isdigit():
                    # Native glyph side bearings provide the space after 병.
                    paste_horizontal(canvas, line.replace(" ", ""),
                                     (0, 7 + row * 21, width, 16), font_image, font_table, graded)
                else:
                    paste_horizontal(canvas, line, (4, 7 + row * 21, width - 8, 16), font_image, font_table, graded)
        else:
            columns = vertical_columns(text)
            # Japanese vertical order: first column on the right.
            for column, line in enumerate(columns):
                x = (width - len(columns) * 16) // 2 + (len(columns) - column - 1) * 16
                paste_vertical(canvas, line, x, 4, height - 8, font_image, font_table, graded)
        assert canvas.size == source.size and canvas.getpalette() == source.getpalette()
        output = directory / f"{stem}.kor.png"
        canvas.save(output)
        generated.append(output)
        print(f"Saved {output}")
    return generated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--font", type=Path, help="TrueType font; omit to use BISCO")
    parser.add_argument("--graded", action="store_true", help="4x grayscale rendering and native palette coverage levels")
    parser.add_argument("--titles-only", action="store_true", help="generate only the five yellow title images")
    parser.add_argument("--title-edge", choices=("warm", "teal", "soft-teal", "soft-warm"), default="warm", help="palette colors for graded title edges")
    parser.add_argument("--white-native", action="store_true", help="only white backgrounds, unchanged 16x16 BISCO glyphs")
    args = parser.parse_args()
    make_sopen(args.directory, args.font, args.graded, args.titles_only, args.title_edge, args.white_native)


if __name__ == "__main__":
    main()
