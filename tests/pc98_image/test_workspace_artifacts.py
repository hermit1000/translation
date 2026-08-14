from shutil import copyfile

from gspecific.taikou1.decode_raw_planar import decode_file as decode_raw
from gspecific.taikou1.decode_rle_lz import decode_file as decode_rle_lz_file
from gspecific.taikou1.encode_raw_planar import encode_folder as encode_raw
from gspecific.taikou1.encode_rle_lz import encode_folder as encode_rle_lz_folder
from gspecific.taikou1.pc98_image_codec import (
    decode_rle_lz,
    encode_planar_indices,
    encode_rle_lz_groups,
)


def test_raw_planar_workspace_artifact_round_trip(tmp_path):
    source = tmp_path / "jpn-pc98/IMAGE.PUT"
    output = tmp_path / "image-pc98/IMAGE.PUT"
    source.parent.mkdir(parents=True)
    indices = bytes(range(8)) * 2
    planar = encode_planar_indices(indices, 16, 1, 3)
    source.write_bytes(planar)

    decode_raw(source, output, 16, 1, 3)

    assert {path.name for path in output.iterdir()} == {
        "000000.jpn.png",
        "log.json",
        "report.html",
    }
    copyfile(output / "000000.jpn.png", output / "000000.kor.png")

    encode_raw(source, output, 16, 1, 3)
    assert (output / "000000.pln.kor.bin").read_bytes() == planar
    assert (output / "log.json").is_file()


def test_rle_lz_workspace_artifact_round_trip(tmp_path):
    source = tmp_path / "jpn-pc98/IMAGE.DAT"
    output = tmp_path / "image-pc98/IMAGE.DAT"
    source.parent.mkdir(parents=True)
    rows = [[(0x0, 0x0, 0x0), (0xF, 0x0, 0x0)]]
    encoded = encode_rle_lz_groups(8, 1, rows)
    source.write_bytes(encoded)

    decode_rle_lz_file(source, output, offset_names=True)

    assert {path.name for path in output.iterdir()} == {
        "000000.jpn.png",
        "log.json",
        "report.html",
    }
    copyfile(output / "000000.jpn.png", output / "000000.kor.png")

    encode_rle_lz_folder(source, output, padding=True)
    rebuilt = (output / "000000.cmp.kor.bin").read_bytes()
    _image, _planar, actual, _info = decode_rle_lz(rebuilt)
    _image, _planar, expected, _info = decode_rle_lz(encoded)
    assert actual == expected
    assert (output / "log.json").is_file()


def test_all_artifacts_opt_in(tmp_path):
    source = tmp_path / "jpn-pc98/IMAGE.PUT"
    output = tmp_path / "image-pc98/IMAGE.PUT"
    source.parent.mkdir(parents=True)
    indices = bytes(range(8)) * 2
    planar = encode_planar_indices(indices, 16, 1, 3)
    source.write_bytes(planar)

    decode_raw(source, output, 16, 1, 3, all_artifacts=True)

    assert (output / "000000.pln.jpn.bin").read_bytes() == planar
    assert (output / "000000.idx.jpn.bin").read_bytes() == indices
    assert (output / "000000.meta.json").is_file()
    assert (output / "log.json").is_file()
    assert (output / "report.html").is_file()
    assert (output / "sheet.png").is_file()
