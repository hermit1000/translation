from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from module.font_image import return_img_roi
from module.font_table import FontTable


TEST_GLYPHS = "가각"
MODE = "table"  # "table", "ttf", or "font_canvas"
TTF_FONT = Path("c:/work_han/font_ext/ext/Cafe24Oneprettynight.ttf")
TTF_SIZE = 17
MULTI_GLYPH_SIZE = 10
THRESHOLD = 170
HORIZONTAL_SCALE = 1.0
X_OFFSET = 0
SOURCE_FONT = Path("c:/work_han/font_update_db/nobu5-BISCO.bmp")
SOURCE_KANJI = Path("c:/work_han/workspace5/jpn-pc98/KANJI.NB5")
KANJI_KOR_TABLE = Path("font_table/font_table-jpn-nb5-kanji-kor.tsv")
KANJI_KOR_COLUMN = "original_kor"
FONT_TABLE = Path("font_table/font_table-kor-jin.json")
OUTPUT_PATH = Path("c:/work_han/workspace5/kor-pc98/KANJI.NB5")
GLYPH_COUNT = 188
GLYPH_SIZE = 16
GLYPH_BYTES = 32


def resolve_path(path: Path) -> Path:
    if path.exists():
        return path
    path_text = str(path)
    if len(path_text) >= 3 and path_text[1:3] == ":/":
        wsl_path = Path("/mnt") / path_text[0].lower() / path_text[3:]
        if wsl_path.exists() or wsl_path.parent.exists():
            return wsl_path
    return path


def pack_glyph(image: Image.Image) -> bytes:
    if image.size != (GLYPH_SIZE, GLYPH_SIZE):
        raise ValueError(f"glyph image must be {GLYPH_SIZE}x{GLYPH_SIZE}: {image.size}")

    data = bytearray()
    for y in range(GLYPH_SIZE):
        for x_byte in range(2):
            value = 0
            for bit in range(8):
                x = x_byte * 8 + bit
                if image.getpixel((x, y)) > 0:
                    value |= 0x80 >> bit
            data.append(value)
    return bytes(data)


def threshold_image(image: Image.Image, threshold: int) -> Image.Image:
    output = Image.new("L", image.size, 0)
    for y in range(image.height):
        for x in range(image.width):
            if image.getpixel((x, y)) < threshold:
                output.putpixel((x, y), 255)
    return output


def load_glyph_from_ttf(font_path: Path, glyph: str) -> Image.Image:
    font_size = MULTI_GLYPH_SIZE if len(glyph) > 1 else TTF_SIZE
    font = ImageFont.truetype(str(font_path), font_size)
    render_width = GLYPH_SIZE * 2
    render_height = GLYPH_SIZE * 2
    image = Image.new("L", (render_width, render_height), 255)
    draw = ImageDraw.Draw(image)
    bbox = draw.textbbox((0, 0), glyph, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = (render_width - width) // 2 - bbox[0]
    y = (render_height - height) // 2 - bbox[1]
    draw.text((x, y), glyph, font=font, fill=0)

    cropped = image.crop(
        (
            (render_width - GLYPH_SIZE) // 2,
            (render_height - GLYPH_SIZE) // 2,
            (render_width + GLYPH_SIZE) // 2,
            (render_height + GLYPH_SIZE) // 2,
        )
    )
    horizontal_scale = 1.0 if len(glyph) > 1 else HORIZONTAL_SCALE
    if horizontal_scale != 1:
        scaled_width = max(1, round(GLYPH_SIZE * horizontal_scale))
        scaled = cropped.resize((scaled_width, GLYPH_SIZE), Image.Resampling.BICUBIC)
        canvas = Image.new("L", (GLYPH_SIZE, GLYPH_SIZE), 255)
        if scaled_width <= GLYPH_SIZE:
            canvas.paste(scaled, ((GLYPH_SIZE - scaled_width) // 2 + X_OFFSET, 0))
        else:
            left = (scaled_width - GLYPH_SIZE) // 2 - X_OFFSET
            canvas.paste(scaled.crop((left, 0, left + GLYPH_SIZE, GLYPH_SIZE)), (0, 0))
        cropped = canvas

    return threshold_image(cropped, THRESHOLD)


def load_glyph_from_font_canvas(font_path: Path, font_table_path: Path, glyph: str) -> Image.Image:
    font_table = FontTable(font_table_path)
    code = font_table.get_code(glyph)
    if code is None:
        raise ValueError(f"{glyph} is not in {font_table_path}")

    source = Image.open(font_path).convert("L")
    y0, y1, x0, x1 = return_img_roi(code)
    glyph = source.crop((x0, y0, x1, y1))
    if glyph.size != (GLYPH_SIZE, GLYPH_SIZE):
        raise ValueError(f"source glyph must be 16x16: {font_path} {glyph.size}")

    # Font canvases are black-on-white; KANJI.NB5 masks use set bits as foreground.
    output = Image.new("L", (16, 16), 0)
    for y in range(16):
        for x in range(16):
            if glyph.getpixel((x, y)) == 0:
                output.putpixel((x, y), 255)
    return output


def load_test_glyph(glyph: str) -> Image.Image:
    if MODE == "ttf":
        return load_glyph_from_ttf(resolve_path(TTF_FONT), glyph)
    if MODE == "font_canvas":
        return load_glyph_from_font_canvas(resolve_path(SOURCE_FONT), FONT_TABLE, glyph)
    raise ValueError(f"Unsupported MODE: {MODE}")


def load_kanji_kor_rows(path: Path) -> list[tuple[str, str, str]]:
    rows = []
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    try:
        korean_index = header.index(KANJI_KOR_COLUMN)
    except ValueError as exc:
        raise ValueError(f"{KANJI_KOR_COLUMN} column is missing in {path}") from exc

    for line in lines[1:]:
        columns = line.split("\t")
        if len(columns) <= korean_index:
            raise ValueError(f"Invalid row: {line}")
        code, japanese = columns[:2]
        korean = columns[korean_index]
        rows.append((code, japanese, korean))
    if len(rows) != GLYPH_COUNT:
        raise ValueError(f"{path} must contain {GLYPH_COUNT} rows, got {len(rows)}")
    return rows


def build_from_table() -> bytes:
    rows = load_kanji_kor_rows(KANJI_KOR_TABLE)
    source_data = resolve_path(SOURCE_KANJI).read_bytes()
    if len(source_data) != GLYPH_COUNT * GLYPH_BYTES:
        raise ValueError(f"Unexpected source KANJI.NB5 size: {len(source_data)}")

    output = bytearray()
    for index, (_, _, korean) in enumerate(rows):
        if korean:
            output.extend(pack_glyph(load_glyph_from_ttf(resolve_path(TTF_FONT), korean)))
        else:
            start = index * GLYPH_BYTES
            output.extend(source_data[start : start + GLYPH_BYTES])
    return bytes(output)


def main() -> None:
    output_path = resolve_path(OUTPUT_PATH)
    if MODE == "table":
        data = build_from_table()
        source_label = str(KANJI_KOR_TABLE)
    else:
        packed_glyphs = [pack_glyph(load_test_glyph(glyph)) for glyph in TEST_GLYPHS]
        data = b"".join(packed_glyphs[index % len(packed_glyphs)] for index in range(GLYPH_COUNT))
        source_label = TEST_GLYPHS
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    print(
        f"{output_path}: wrote {GLYPH_COUNT} glyphs from '{source_label}' "
        f"({output_path.stat().st_size} bytes, mode={MODE})"
    )


if __name__ == "__main__":
    main()
