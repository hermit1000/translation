from gspecific.garyou.end_dat_to_png import IMAGE_SIZE, planar_to_indices
from gspecific.garyou.end_png_to_dat import indices_to_planar
from gspecific.taikou1.pc98_image_codec import (
    decode_planar,
    encode_planar_indices,
)


def test_taikou_interleaved_wrapper_round_trip():
    indices = bytes(index % 8 for index in range(16))
    planar = encode_planar_indices(indices, 16, 1, 3)
    _image, decoded = decode_planar(planar, 16, 1, 3)
    assert decoded == indices


def test_garyou_split_screen_wrapper_round_trip():
    planar = bytes((index * 17) & 0xFF for index in range(IMAGE_SIZE))
    assert indices_to_planar(planar_to_indices(planar)) == planar
