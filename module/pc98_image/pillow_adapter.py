"""Pillow adapters kept separate from binary format primitives."""

from collections.abc import Sequence

from PIL import Image

from .indexed import Color, IndexedImage
from .palette import nearest_palette_index


def to_pillow(image: IndexedImage) -> Image.Image:
    if image.palette is None:
        raise ValueError("an indexed Pillow image requires a palette")
    output = Image.frombytes("P", (image.width, image.height), image.indices)
    flat_palette = [component for color in image.palette for component in color]
    output.putpalette(flat_palette + [0] * (768 - len(flat_palette)))
    return output


def from_pillow(source: Image.Image, palette: Sequence[Color]) -> IndexedImage:
    image = source.convert("RGB")
    indices = bytes(nearest_palette_index(rgb, palette) for rgb in image.getdata())
    return IndexedImage.create(image.width, image.height, indices, palette)
