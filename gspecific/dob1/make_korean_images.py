"""Generate all Korean title-screen PNGs for Dead of the Brain PC-98."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FRR_LAYOUT = (
    # text, x, y, font size
    ("데드", 10, 27, 24),
    ("오브", 62, 29, 13),
    ("더", 28, 56, 13),
    ("브레인", 48, 50, 24),
)
FRR_SHADOW_INDEX = 2
FRR_TEXT_INDEX = 15
FRR_Y_OFFSET = 2

BLTY_UPPER_TEXT = "데드 오브 더 브레인"
BLTY_UPPER_INDEX = 11
BLTY_RED_INDEX = 12
BLTY_CYAN_INDEX = 13
BLTY_SUBTITLE_SIZE = (160, 65)
BLTY_SUBTITLE_CENTER_X = 366
BLTY_SUBTITLE_Y = 205


def normalize_indexed(image: Image.Image, reference: Image.Image) -> Image.Image:
    """Return an indexed copy using the reference's exact 16-color palette."""
    if image.mode == "P":
        return image.copy()
    if reference.mode != "P":
        raise ValueError("palette reference must be an indexed PNG")
    palette = reference.getpalette()
    color_to_index = {
        tuple(palette[index * 3 : index * 3 + 3]): index for index in range(16)
    }
    rgb = image.convert("RGB")
    indices = []
    for color in rgb.getdata():
        if color not in color_to_index:
            raise ValueError(f"image contains an unknown palette color {color}")
        indices.append(color_to_index[color])
    indexed = Image.new("P", image.size)
    indexed.putpalette(palette)
    indexed.putdata(indices)
    return indexed


def default_bold_font() -> Path:
    path = Path(r"C:\Windows\Fonts\HANBatangB.ttf")
    if not path.is_file():
        raise FileNotFoundError("pass a bold Korean Myeongjo font with --font")
    return path


def text_mask(text: str, font: ImageFont.FreeTypeFont) -> Image.Image:
    bounds = font.getbbox(text)
    mask = Image.new("1", (bounds[2] - bounds[0], bounds[3] - bounds[1]))
    ImageDraw.Draw(mask).text(
        (-bounds[0], -bounds[1]), text, font=font, fill=1, stroke_width=0
    )
    return mask


def render_frr(root: Path, workspace: Path, bold_font: Path) -> Path:
    source = root / "FRR.bg.png"
    reference = workspace / "image-pc98" / "GRAPH" / "FRR.GPC" / "FRR.jpn.png"
    output = root / "FRR.kor.png"
    image = normalize_indexed(Image.open(source), Image.open(reference))
    if image.size != (640, 400):
        raise ValueError("FRR background must be 640x400")

    for text, x, y, size in FRR_LAYOUT:
        mask = text_mask(text, ImageFont.truetype(str(bold_font), size))
        y += FRR_Y_OFFSET
        image.paste(FRR_SHADOW_INDEX, (x + 1, y + 1), mask)
        image.paste(FRR_TEXT_INDEX, (x, y), mask)
    image.save(output, optimize=True)
    return output


def render_blty_upper(image: Image.Image, bold_font: Path) -> None:
    regular_font = bold_font.with_name("HANBatang.ttf")
    if not regular_font.is_file():
        regular_font = bold_font
    mask = text_mask(
        BLTY_UPPER_TEXT, ImageFont.truetype(str(regular_font), 14)
    )
    x = 307 - mask.width // 2
    image.paste(BLTY_UPPER_INDEX, (x, 89), mask)


def horror_subtitle_masks(
    source: Path,
) -> tuple[Image.Image, Image.Image, Image.Image]:
    generated = Image.open(source).convert("L")
    ink = generated.point(lambda value: 255 - value)
    bbox = ink.point(lambda value: 255 if value >= 20 else 0).getbbox()
    if bbox is None:
        raise ValueError(f"no non-white lettering found in {source}")

    mask = ink.crop(bbox).resize(BLTY_SUBTITLE_SIZE, Image.Resampling.LANCZOS)
    mask = mask.point(lambda value: 255 if value >= 72 else 0)

    # The possessive 의 echoes the smaller Japanese の in the original layout.
    particle_box = (66, 0, 94, BLTY_SUBTITLE_SIZE[1])
    particle = mask.crop(particle_box).resize((22, 52), Image.Resampling.NEAREST)
    mask.paste(0, particle_box)
    mask.paste(particle, (69, 4), particle)

    outline = mask.filter(ImageFilter.MaxFilter(3))
    red = mask.copy()
    scratches = ImageDraw.Draw(red)
    for x, y1, y2 in (
        (12, 13, 31), (27, 20, 39),
        (43, 10, 27), (57, 25, 45),
        (76, 12, 27), (87, 22, 39),
        (108, 11, 29), (121, 23, 42),
        (139, 9, 28), (151, 20, 40),
    ):
        scratches.line((x, y1, x, y2), fill=0, width=1)
    return mask, outline, red


def render_blty(root: Path, bold_font: Path) -> tuple[Path, Path, Path]:
    source = root / "BLTY_AB.bg.png"
    reference = root / "BLTY_AB.jpn.png"
    subtitle_source = root / "BLTY_AB.subtitle.imagegen.png"
    combined_output = root / "BLTY_AB.kor.png"
    upper_output = root / "BLTY_A.kor.png"
    lower_output = root / "BLTY_B.kor.png"

    image = normalize_indexed(Image.open(source), Image.open(reference))
    if image.size != (640, 400):
        raise ValueError("BLTY background must be 640x400")
    render_blty_upper(image, bold_font)

    mask, outline, red = horror_subtitle_masks(subtitle_source)
    left = BLTY_SUBTITLE_CENTER_X - BLTY_SUBTITLE_SIZE[0] // 2
    y = BLTY_SUBTITLE_Y
    # Subtle down/right cyan backing between the old 1px and 2px variants.
    image.paste(BLTY_CYAN_INDEX, (left + 1, y + 2), mask)
    image.paste(BLTY_CYAN_INDEX, (left, y), outline)
    image.paste(BLTY_RED_INDEX, (left, y), red)

    image.save(combined_output, optimize=True)
    image.crop((0, 0, 640, 201)).save(upper_output, optimize=True)
    image.crop((0, 201, 640, 400)).save(lower_output, optimize=True)
    return combined_output, upper_output, lower_output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--font", type=Path)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    root = workspace / "binary_inputs-pc98"
    font = args.font.resolve() if args.font else default_bold_font()

    frr = render_frr(root, workspace, font)
    blty, blty_a, blty_b = render_blty(root, font)
    print(f"wrote: {frr}")
    print(f"wrote: {blty}")
    print(f"wrote: {blty_a}")
    print(f"wrote: {blty_b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
