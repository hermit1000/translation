"""Shared primitives for indexed PC-98 images."""

from .indexed import IndexedImage
from .palette import (
    PC98_PALETTE_3BPP,
    PC98_PALETTE_4BPP,
    decode_4bit_palette,
    nearest_palette_index,
)
from .planar import (
    decode_interleaved_planar,
    decode_plane_major_column_planar,
    decode_plane_major_row_planar,
    encode_interleaved_planar,
    encode_plane_major_column_planar,
    encode_plane_major_row_planar,
)

__all__ = [
    "IndexedImage",
    "PC98_PALETTE_3BPP",
    "PC98_PALETTE_4BPP",
    "decode_4bit_palette",
    "decode_interleaved_planar",
    "decode_plane_major_column_planar",
    "decode_plane_major_row_planar",
    "encode_interleaved_planar",
    "encode_plane_major_column_planar",
    "encode_plane_major_row_planar",
    "nearest_palette_index",
]
