import struct

import pytest

from module.pc98_image.formats.adv98_gpc import (
    decode_gpc, encode_gpc, pack_zero_masks,
)


def fixture_gpc(*, variant="standard", interlace=1, height=1):
    # Fixed encoded row: runtime reconstruction is [1, 1, 3, 7].
    stream = pack_zero_masks(bytes((2, 1, 2, 2, 6)) * height + bytes((-5 * height) % 64))
    data = bytearray(0x64)
    data[:16] = b"PC98)GPCFILE   \0"
    struct.pack_into("<H", data, 0x10, interlace)
    struct.pack_into("<II", data, 0x14, 0x30, 0x54)
    struct.pack_into("<I", data, 0x20, 0 if variant == "necronomicon" else len(data) + len(stream))
    struct.pack_into("<HH", data, 0x30, 16, 2)
    struct.pack_into("<H", data, 0x38, 0x0080)
    stored_size = len(stream) + (16 if variant == "necronomicon" else 0)
    struct.pack_into("<8H", data, 0x54, 8, height, stored_size, 0, 4, 0, 0, 0)
    return bytes(data) + stream


@pytest.mark.parametrize("variant", ["standard", "necronomicon"])
@pytest.mark.parametrize("interlace", [1, 2])
@pytest.mark.parametrize("cumulative_xor", [True, False])
def test_shared_encoding_roundtrip_preserves_header_variant_and_interlace(variant, interlace, cumulative_xor):
    source = fixture_gpc(variant=variant, interlace=interlace, height=4)
    indices = bytes((i * 7 + 3) % 16 for i in range(32))
    encoded, planar = encode_gpc(
        source, indices, variant=variant, cumulative_xor=cumulative_xor,
    )
    decoded = decode_gpc(encoded, variant=variant, cumulative_xor=cumulative_xor)
    assert decoded.indices == indices
    assert decoded.interlace == interlace
    assert len(planar) == 16
    if variant == "necronomicon":
        assert struct.unpack_from("<I", encoded, 0x20)[0] == 0
        assert struct.unpack_from("<H", encoded, 0x58)[0] == decoded.compressed_size + 16
    else:
        assert struct.unpack_from("<I", encoded, 0x20)[0] == len(encoded)


def test_game_facades_use_shared_codec_and_preserve_palette_selection():
    from gspecific.dob1 import gpc as dob1
    from gspecific.dob1.encode_korean_images import encode_standard_gpc
    from gspecific.dracula.decode_gpc import decode_dracula_gpc
    from gspecific.necronomicon.decode_gpc import decode_necronomicon_gpc

    assert dob1.decode_gpc is decode_gpc
    assert encode_standard_gpc is encode_gpc
    common = decode_gpc(fixture_gpc())
    dracula = decode_dracula_gpc(fixture_gpc())
    necro = decode_necronomicon_gpc(fixture_gpc(variant="necronomicon"))
    assert common.planar == dracula.planar == necro.planar == bytes((1, 1, 3, 7))
    assert common.palette[2] == (136, 0, 0)
    assert dracula.palette[2] == necro.palette[2] == (138, 0, 0)


def test_shared_artifact_writer_keeps_pngs_in_selected_directory(tmp_path):
    from module.pc98_image.adv98_artifacts import write_artifacts

    source = tmp_path / "jpn-pc98" / "GPC" / "SAMPLE.GPC"
    source.parent.mkdir(parents=True)
    source.write_bytes(fixture_gpc())
    binary_dir = tmp_path / "image-pc98" / "GPC" / source.name
    png_dir = tmp_path / "image-pc98" / "png"
    write_artifacts(source, binary_dir, png_output=png_dir)
    assert (png_dir / "SAMPLE.jpn.png").is_file()
    assert not (binary_dir / "SAMPLE.jpn.png").exists()
    assert (binary_dir / "SAMPLE.idx.jpn.bin").is_file()
    assert (binary_dir / "SAMPLE.meta.json").is_file()
