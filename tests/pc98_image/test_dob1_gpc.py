import struct

from gspecific.dob1.gpc import (
    apply_output_mode,
    decode_packed_palette,
    pack_zero_masks,
    undo_xor_delta,
    unpack_zero_masks,
)


def test_unpack_zero_masks_mixes_zero_and_literal_groups():
    packed = bytes((0x80, 0xA0, 0x12, 0x34))
    unpacked, consumed = unpack_zero_masks(packed, 64)
    assert consumed == len(packed)
    assert unpacked[:8] == bytes((0x12, 0, 0x34, 0, 0, 0, 0, 0))
    assert unpacked[8:] == bytes(56)


def test_pack_zero_masks_roundtrip():
    expanded = bytes(range(64)) + bytes(64)
    packed = pack_zero_masks(expanded)
    unpacked, consumed = unpack_zero_masks(packed, len(expanded))
    assert unpacked == expanded
    assert consumed == len(packed)


def test_undo_xor_delta_uses_row_stride():
    assert undo_xor_delta(bytes((2, 1, 2, 2, 6, 7, 14))) == bytes((1, 2, 3, 4, 4, 10))


def test_decode_packed_palette_uses_0grb_words():
    words = [0x0000, 0x0FFF] + [0] * 14
    palette = decode_packed_palette(b"".join(struct.pack("<H", word) for word in words))
    assert palette[0] == (0, 0, 0)
    assert palette[1] == (255, 255, 255)


def test_both_output_modes_apply_cumulative_row_xor():
    rows = [bytes((1, 2)), bytes((3, 6)), bytes((7, 14))]
    expected = [
        bytes((1, 2)),
        bytes((2, 4)),
        bytes((5, 10)),
    ]
    assert apply_output_mode(rows, 0) == expected
    assert apply_output_mode(rows, 1) == expected
