import json

import pytest

from module.name_db import NameDB


def write_database(db_dir):
    databases = {
        "full_name_db.json": {
            "北条 氏康": {"kor": "호조 우지야스", "game": ["nb4"]},
        },
        "family_name_db.json": {
            "北条": {"kor": "호조", "code": {"nb4": "AABB"}},
        },
        "given_name_db.json": {
            "氏康": {"kor": "우지야스"},
        },
    }
    for file_name, data in databases.items():
        (db_dir / file_name).write_text(
            json.dumps(data, ensure_ascii=False),
            encoding="utf-8",
            newline="\r\n",
        )


def test_query_and_code_index(tmp_path):
    write_database(tmp_path)
    db = NameDB(tmp_path)

    assert db.get_korean_name("北条 氏康", "nb4").family == "호조"
    assert db.get_korean_name("北条 氏康", "nb3") is None
    assert list(db.iter_full_names("nb4"))[0][0] == "北条 氏康"
    assert db.find_name_by_code("family", "0x:AABB", "nb4") == "北条"
    assert db.validate() == []


def test_add_full_name_uses_exact_component_translation(tmp_path):
    write_database(tmp_path)
    db = NameDB(tmp_path)

    with pytest.raises(ValueError):
        db.add_full_name("北条 氏政", "호 우지마사", "nb4")


def test_save_uses_injected_directory(tmp_path):
    write_database(tmp_path)
    db = NameDB(tmp_path)
    db.add_game("北条 氏康", "taiko1")
    db.save_db()

    saved = json.loads((tmp_path / "full_name_db.json").read_text(encoding="utf-8"))
    assert saved["北条 氏康"]["game"] == ["nb4", "taiko1"]
