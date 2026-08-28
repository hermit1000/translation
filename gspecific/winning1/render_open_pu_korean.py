#!/usr/bin/env python3
"""Render Korean Power-Up Kit text into Winning Post OPEN_PU sprites."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DEFAULT_WORKSPACE = Path(r"C:\work_han\workspace3")
DEFAULT_FONT = Path(r"C:\work_han\font_ext\ext\나눔\NanumGothicExtraBold.ttf")
TEXT = "파워업키트"

# The first OPEN_PU block is the logo-only animation layer. The two blocks
# below contain the large Japanese Power-Up Kit lettering.
SPRITES = {
    "0034a2": {"size": (520, 152), "background_top": 30, "text_top": 30, "font_size": 78},
    "007435": {"size": (368, 200), "background_top": 140, "text_top": 124, "font_size": 51},
}


def load_indices(path: Path, size: tuple[int, int]) -> Image.Image:
    data = path.read_bytes()
    expected = size[0] * size[1]
    if len(data) != expected:
        raise ValueError(f"{path}: expected {expected} index bytes, got {len(data)}")
    return Image.frombytes("L", size, data)


def analyze(indices: Image.Image, text_top: int) -> None:
    region = indices.crop((0, text_top, indices.width, indices.height))
    print(Counter(region.getdata()).most_common())


def render(
    indices: Image.Image,
    background_top: int,
    text_top: int,
    font_path: Path,
    font_size: int,
) -> tuple[Image.Image, Image.Image]:
    # OPEN_PU sprites use index 14 as the transparent/background key in the
    # 0034a2 layer and index 0 in the already-composited 007435 layer.
    background = indices.getpixel((0, indices.height - 1))
    region = indices.crop((0, text_top, indices.width, indices.height))
    counts = Counter(region.getdata())
    ink_candidates = [index for index, _ in counts.most_common() if index != background]
    if len(ink_candidates) < 2:
        raise ValueError("could not identify OPEN_PU text and shadow indices")
    ink, shadow = ink_candidates[:2]

    background_image = indices.copy()
    ImageDraw.Draw(background_image).rectangle(
        (0, background_top, indices.width - 1, indices.height - 1), fill=background
    )
    result = indices.copy()
    ImageDraw.Draw(result).rectangle(
        (0, text_top, indices.width - 1, indices.height - 1), fill=background
    )

    font = ImageFont.truetype(str(font_path), font_size)
    scratch = Image.new("L", (indices.width * 2, indices.height), 0)
    ImageDraw.Draw(scratch).text((0, 0), TEXT, font=font, fill=255, stroke_width=1, stroke_fill=255)
    box = scratch.getbbox()
    if box is None:
        raise ValueError("font rendered no foreground pixels")
    mask = scratch.crop(box).point(lambda value: 255 if value >= 128 else 0)

    available_height = indices.height - text_top - 12
    scale = min((indices.width - 16) / mask.width, available_height / mask.height)
    mask = mask.resize(
        (max(1, round(mask.width * scale)), max(1, round(mask.height * scale))),
        Image.Resampling.NEAREST,
    )
    x = (indices.width - mask.width) // 2
    y = text_top + max(0, (available_height - mask.height) // 2)
    shadow_image = Image.new("L", mask.size, shadow)
    ink_image = Image.new("L", mask.size, ink)
    result.paste(shadow_image, (x + 2, y + 2), mask)
    result.paste(ink_image, (x, y), mask)

    # Preserve the characteristic underline, including its one-pixel shadow.
    line_y = indices.height - 7
    draw = ImageDraw.Draw(result)
    draw.rectangle((8, line_y + 2, indices.width - 7, line_y + 4), fill=shadow)
    draw.rectangle((6, line_y, indices.width - 9, line_y + 2), fill=ink)
    return background_image, result


def save_indexed_png(path: Path, indices: Image.Image) -> None:
    palette = [
        (0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255),
        (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255),
        (128, 128, 128), (128, 128, 255), (255, 128, 128), (255, 128, 255),
        (128, 255, 128), (128, 255, 255), (255, 255, 128), (255, 255, 255),
    ]
    # Keep editable PNGs consistent with decoder output.  Saving a P-mode
    # image here (or converting it to RGBA during later compositing) makes the
    # manually edited files differ in mode from their RGB source images.
    # Materialize palette indices as RGB pixels before writing instead.
    rgb = bytes(
        component
        for index in indices.getdata()
        for component in palette[index]
    )
    output = Image.frombytes("RGB", indices.size, rgb)
    path.parent.mkdir(parents=True, exist_ok=True)
    output.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()

    source_root = args.workspace / "image-pc98" / "OPEN_PU.DAT"
    output_root = args.output_root or args.workspace / "binary_inputs-pc98" / "OPEN_PU.DAT"
    for stem, config in SPRITES.items():
        source = source_root / f"{stem}.idx.jpn.bin"
        indices = load_indices(source, config["size"])
        if args.analyze:
            print(f"{stem}:", end=" ")
            analyze(indices, config["text_top"])
            continue
        background, localized = render(
            indices,
            config["background_top"],
            config["text_top"],
            args.font,
            config["font_size"],
        )
        background_output = output_root / f"{stem}.bg.png"
        output = output_root / f"{stem}.kor.png"
        save_indexed_png(background_output, background)
        save_indexed_png(output, localized)
        print(f"{source} -> {background_output}, {output}")


if __name__ == "__main__":
    main()
