import pytest

from module.pc98_image.indexed import IndexedImage
from module.pc98_image.palette import (
    decode_4bit_palette,
    encode_4bit_palette,
    nearest_palette_index,
)
from module.pc98_image.planar import (
    decode_interleaved_planar,
    decode_packed_4bpp,
    decode_plane_major_column_planar,
    decode_plane_major_row_planar,
    encode_interleaved_planar,
    encode_packed_4bpp,
    encode_plane_major_column_planar,
    encode_plane_major_row_planar,
)


@pytest.mark.parametrize("planes", [3, 4])
def test_all_planar_layouts_round_trip(planes):
    width = 16
    height = 3
    indices = bytes(index % (1 << planes) for index in range(width * height))
    layouts = (
        (encode_interleaved_planar, decode_interleaved_planar),
        (encode_plane_major_row_planar, decode_plane_major_row_planar),
        (encode_plane_major_column_planar, decode_plane_major_column_planar),
    )

    for encode, decode in layouts:
        encoded = encode(indices, width, height, planes)
        assert decode(encoded, width, height, planes) == indices


def test_interleaved_plane_order_is_low_bit_first():
    indices = bytes(range(8))
    assert encode_interleaved_planar(indices, 8, 1, 3) == b"\x55\x33\x0f"


def test_packed_4bpp_uses_scanline_padding():
    indices = bytes([1, 2, 3, 4, 5, 6])
    packed = encode_packed_4bpp(indices, 3, 2)
    assert packed == b"\x12\x30\x45\x60"
    assert decode_packed_4bpp(packed, 3, 2) == indices


def test_palette_codec_and_matching():
    raw = bytes((0, 1, 2, 15, 14, 13))
    palette = decode_4bit_palette(raw, order="brg")
    assert palette == ((17, 34, 0), (238, 221, 255))
    assert encode_4bit_palette(palette, order="brg") == raw
    assert nearest_palette_index((16, 34, 0), palette) == 0


def test_indexed_image_validates_indices():
    with pytest.raises(ValueError, match="outside the palette"):
        IndexedImage.create(1, 1, b"\x02", [(0, 0, 0), (255, 255, 255)])
