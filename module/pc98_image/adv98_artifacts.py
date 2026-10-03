"""Shared ADV98 image artifact writing and exact PNG palette mapping."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from PIL import Image

from .formats.adv98_gpc import GPCImage, decode_gpc
from .indexed import IndexedImage
from .pillow_adapter import to_pillow


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


def write_artifacts(
    source: Path,
    output: Path,
    *,
    output_mode: int = 0,
    observed_modes: dict[int, int] | None = None,
    decoder: Callable[..., GPCImage] = decode_gpc,
    png_output: Path | None = None,
) -> GPCImage:
    data = source.read_bytes()
    decoded = decoder(data, output_mode=output_mode)
    output.mkdir(parents=True, exist_ok=True)
    stem = source.stem

    (output / f"{stem}.jpn{source.suffix}").write_bytes(data)
    (output / f"{stem}.pln.jpn.bin").write_bytes(decoded.planar)
    (output / f"{stem}.idx.jpn.bin").write_bytes(decoded.indices)
    image = IndexedImage.create(
        decoded.width, decoded.height, decoded.indices, decoded.palette
    )
    png_directory = png_output if png_output is not None else output
    png_directory.mkdir(parents=True, exist_ok=True)
    to_pillow(image).save(png_directory / f"{stem}.jpn.png")

    metadata = {
        "source": str(source.relative_to(source.parents[1])).replace("\\", "/"),
        "offset": "0x000000",
        "original_size": decoded.source_size,
        "encoded_size": None,
        "stored_size": None,
        "padding_byte": None,
        "compression": "adv98-gpc-zero-mask-xor",
        "width": decoded.width,
        "height": decoded.height,
        "planes": decoded.descriptor_planes,
        "plane_order": "BRGI",
        "planar_layout": "row-major-plane-interlaced",
        "bit_order": "msb-first",
        "stride": (decoded.width + 7) // 8,
        "planar_segments": decoded.interlace,
        "palette": "embedded-0x0GRB",
        "palette_offset": f"0x{decoded.palette_offset:06X}",
        "descriptor_offset": f"0x{decoded.descriptor_offset:06X}",
        "compressed_offset": f"0x{decoded.compressed_offset:06X}",
        "compressed_size": decoded.compressed_size,
        "compressed_consumed": decoded.compressed_consumed,
        "compressed_padding_size": decoded.compressed_padding_size,
        "display_x": decoded.x,
        "display_y": decoded.y,
        "descriptor_unknown_06": decoded.descriptor_unknown_06,
        "descriptor_flags": decoded.descriptor_flags,
        "output_mode": decoded.output_mode,
        "observed_output_modes": {
            str(mode): count for mode, count in sorted((observed_modes or {}).items())
        },
    }
    metadata_text = json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    (output / f"{stem}.meta.json").write_text(
        metadata_text.replace("\n", "\r\n"),
        encoding="utf-8",
        newline="",
    )
    return decoded
