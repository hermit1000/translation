#!/usr/bin/env python3
"""Render Korean NAME.BMD label PNGs from a translation table.

The generated PNGs are 64x24 RGB images using the same four colors as the
source labels: black, red, white text, and blue one-pixel shadow.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 64
HEIGHT = 24
WHITE = (255, 255, 255)
BLUE = (0, 0, 255)
VALID_LABEL_COLORS = {
    (0, 0, 0),
    (255, 0, 0),
    WHITE,
    BLUE,
}


def normalize_path(path: Path) -> Path:
    path_text = str(path)
    if len(path_text) >= 3 and path_text[1:3] == ":/":
        drive = path_text[0].lower()
        return Path("/mnt") / drive / path_text[3:]
    return path


def parse_translation_table(path: Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        parts = raw_line.split("\t")
        if len(parts) < 4:
            continue
        filename = parts[0].strip()
        korean = parts[3].strip()
        if not filename.endswith(".jpn.png") or not korean:
            continue

        # Some hand-edited rows may miss the tab before the note column.
        for marker in (" MAIN.EXE", " MESSAGE", " 대사 정확"):
            marker_index = korean.find(marker)
            if marker_index > 0:
                korean = korean[:marker_index].rstrip()
                break
        entries.append((filename.removesuffix(".jpn.png"), korean))
    return entries


def hard_text_mask(text: str, font: ImageFont.FreeTypeFont, threshold: int, stroke_width: int) -> Image.Image:
    probe = Image.new("L", (256, 64), 0)
    draw = ImageDraw.Draw(probe)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).text(
        (-bbox[0], -bbox[1]),
        text,
        font=font,
        fill=255,
        stroke_width=stroke_width,
        stroke_fill=255,
    )
    return mask.point(lambda value: 255 if value >= threshold else 0)


def render_label(
    background: Image.Image,
    text: str,
    font: ImageFont.FreeTypeFont,
    y: int,
    threshold: int,
    stroke_width: int,
    long_threshold: int | None,
    thin_longer_than: int,
    long_x_scale: float,
    scale_texts: set[str],
) -> Image.Image:
    image = background.copy()
    probe_mask = hard_text_mask(text, font, threshold, stroke_width)
    text_width, _text_height = probe_mask.size
    is_long = text_width >= thin_longer_than
    if long_threshold is not None and is_long:
        mask = hard_text_mask(text, font, long_threshold, stroke_width)
    else:
        mask = probe_mask
    should_scale = is_long and long_x_scale != 1.0
    if scale_texts:
        should_scale = text in scale_texts
    if should_scale:
        scaled_width = max(1, round(mask.width * long_x_scale))
        mask = mask.resize((scaled_width, mask.height), Image.Resampling.NEAREST)
    text_width, _text_height = mask.size
    x = (WIDTH - text_width) // 2
    if x < 0:
        x = max(-1, x)

    image.paste(Image.new("RGB", mask.size, BLUE), (x + 1, y + 1), mask)
    image.paste(Image.new("RGB", mask.size, WHITE), (x, y), mask)
    return image


def validate_palette(path: Path) -> None:
    colors = {color for _count, color in Image.open(path).convert("RGB").getcolors(maxcolors=100000)}
    if not colors <= VALID_LABEL_COLORS:
        extra = ", ".join(str(color) for color in sorted(colors - VALID_LABEL_COLORS))
        raise ValueError(f"{path.name} has non-PC98 label colors: {extra}")


def write_contact_sheet(folder: Path, stems: list[str], columns: int, scale: int) -> None:
    if not stems:
        return
    label_height = 14
    padding = 10
    cell_width = WIDTH * scale + padding
    cell_height = HEIGHT * scale + label_height + padding
    rows = (len(stems) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for index, stem in enumerate(stems):
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        draw.text((x, y), stem, fill=(0, 0, 0))
        label = Image.open(folder / f"{stem}.kor.png").convert("RGB")
        sheet.paste(label.resize((WIDTH * scale, HEIGHT * scale), Image.Resampling.NEAREST), (x, y + label_height))
    sheet.save(folder / "contact_sheet.kor.png")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Korean NAME.BMD label PNGs.")
    parser.add_argument(
        "--folder",
        type=Path,
        default=Path("c:/work_han/workspace1/binary_inputs-pc98/NAME.BMD"),
        help="folder containing bg.png and name_bmd_text_translations.txt",
    )
    parser.add_argument(
        "--font",
        type=Path,
        default=Path("c:/work_han/font_ext/ext/Galmuri-v2.40.3/Galmuri9.ttf"),
        help="TrueType font used to render Korean labels",
    )
    parser.add_argument("--text", default="name_bmd_text_translations.txt", help="translation table filename")
    parser.add_argument("--background", default="bg.png", help="label background PNG filename")
    parser.add_argument("--font-size", type=int, default=10)
    parser.add_argument("--text-y", type=int, default=7)
    parser.add_argument("--stroke-width", type=int, default=0)
    parser.add_argument("--threshold", type=int, default=128)
    parser.add_argument("--long-threshold", type=int, default=192)
    parser.add_argument("--thin-longer-than", type=int, default=50)
    parser.add_argument("--long-x-scale", type=float, default=1.0)
    parser.add_argument(
        "--scale-text",
        action="append",
        default=None,
        help="Korean text to x-scale; may be passed multiple times. Overrides width-based scaling.",
    )
    parser.add_argument("--sheet-columns", type=int, default=4)
    parser.add_argument("--sheet-scale", type=int, default=4)
    args = parser.parse_args()

    folder = normalize_path(args.folder).resolve()
    background = Image.open(folder / args.background).convert("RGB")
    if background.size != (WIDTH, HEIGHT):
        raise ValueError(f"{args.background} must be {WIDTH}x{HEIGHT}, got {background.size}")
    font = ImageFont.truetype(str(normalize_path(args.font)), args.font_size)
    entries = parse_translation_table(folder / args.text)
    scale_texts = set(args.scale_text if args.scale_text is not None else ["크래프트타운"])

    written: list[str] = []
    for stem, korean in entries:
        output = folder / f"{stem}.kor.png"
        render_label(
            background,
            korean,
            font,
            args.text_y,
            args.threshold,
            args.stroke_width,
            args.long_threshold,
            args.thin_longer_than,
            args.long_x_scale,
            scale_texts,
        ).save(output)
        validate_palette(output)
        written.append(stem)

    write_contact_sheet(folder, written, args.sheet_columns, args.sheet_scale)
    print(f"wrote {len(written)} Korean NAME.BMD labels below {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
