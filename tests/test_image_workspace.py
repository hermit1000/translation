import json

from gspecific.image_workspace import (
    ImageWorkspace,
    native_artifact_name,
    offset_stem,
    update_meta,
)


def test_image_workspace_uses_standard_platform_directories(tmp_path):
    workspace = ImageWorkspace(tmp_path, "pc98")

    assert workspace.source("DATA/IMAGE.DAT") == tmp_path / "jpn-pc98/DATA/IMAGE.DAT"
    assert workspace.artifacts("DATA/IMAGE.DAT") == tmp_path / "image-pc98/DATA/IMAGE.DAT"


def test_image_artifact_names_preserve_native_extension():
    assert native_artifact_name("END_S3.DAT", "jpn") == "END_S3.jpn.DAT"
    assert native_artifact_name("STR_MENU.OZM", "kor") == "STR_MENU.kor.OZM"
    assert offset_stem(0x180) == "000180"


def test_update_meta_preserves_existing_fields(tmp_path):
    path = tmp_path / "000180.meta.json"
    update_meta(path, source="OPEN.DAT", original_size=32)
    update_meta(path, encoded_size=24)

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "source": "OPEN.DAT",
        "original_size": 32,
        "encoded_size": 24,
    }
