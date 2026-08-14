import copy
from pathlib import Path

from module.pc98_image.formats.olh import OLH
from module.pc98_image.formats.ozm import OZM
from module.pc98_image.planar import decode_plane_major_row_planar
from gspecific.mac1.decode import decompress_img, read_img
from gspecific.mac2.olh import OLH as Mac2OLH

FIXTURES = Path(__file__).parents[1] / "fixtures" / "pc98_image"


def test_olh_sample_round_trip_preserves_indices(tmp_path):
    source = FIXTURES / "C01_07.OLH"
    output_png = tmp_path / "frame.png"
    output_olh = tmp_path / "frame.OLH"

    olh = OLH()
    assert olh.read_olh(source)
    assert len(olh.frames) == 1
    olh.save_frame_as_png(0, output_png)

    encoded = OLH()
    encoded.frames.append(copy.deepcopy(olh.frames[0]))
    encoded.read_png_as_8bpp(output_png)
    encoded.compress(output_olh)

    round_tripped = OLH()
    assert round_tripped.read_olh(output_olh)
    round_tripped.save_frame_as_png(0, tmp_path / "round_tripped.png")

    assert round_tripped.frames[0]["data_8bpp"] == olh.frames[0]["data_8bpp"]


def test_ozm_sample_decodes_and_reencodes_indices(tmp_path):
    source = FIXTURES / "STR_MENU.OZM"
    output_png = tmp_path / "frame.png"
    output_ozm = tmp_path / "frame.OZM"

    ozm = OZM()
    assert ozm.read_ozm(source)
    ozm.decompress()
    ozm.save_as_png(output_png)

    encoded = OZM()
    encoded.palette = ozm.palette
    encoded.read_png_as_8bpp(output_png)
    encoded.compress(output_ozm)

    assert encoded.data_8bpp == ozm.data_8bpp


def test_mac1_sample_uses_row_major_planar_conversion():
    _tag, width, height, compressed = read_img(FIXTURES / "MG09.IMG")
    planar = decompress_img(compressed, width, height)
    indices = decode_plane_major_row_planar(planar, width, height, 4)

    assert len(indices) == width * height
    assert max(indices) <= 15


def test_mac2_codec_decodes_migrated_olh_sample(tmp_path):
    olh = Mac2OLH()
    assert olh.read_olh(FIXTURES / "C01_07.OLH")
    olh.save_frame_as_png(0, tmp_path / "mac2.png")

    assert len(olh.frames) == 1
    assert len(olh.frames[0]["data_8bpp"]) == (
        olh.frames[0]["width"] * olh.frames[0]["height"]
    )
