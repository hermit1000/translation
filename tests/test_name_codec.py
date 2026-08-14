import pytest

from module.name_codec import (
    NamePair,
    align_encoded_length,
    clean_script_name,
    format_korean_name_prefer_given_leading_space,
    format_korean_name_without_added_space,
    pair_korean,
    split_pairs,
)
from module.font_image import add_text_pairs


def test_name_pair_round_trip():
    name = NamePair.parse("北条 氏康")

    assert name.family == "北条"
    assert name.given == "氏康"
    assert str(name) == "北条 氏康"


@pytest.mark.parametrize("value", ["北条", "北条 氏 康", " 北条"])
def test_name_pair_rejects_invalid_shape(value):
    with pytest.raises(ValueError):
        NamePair.parse(value)


def test_script_name_helpers():
    assert clean_script_name("|_北条|␀␀") == "北条"
    assert pair_korean("가나다라") == "{가나}{다라}"
    assert split_pairs("가나다") == (["가나", "다_"], True)

    pairs = set()
    assert not add_text_pairs("가나다", pairs)
    assert pairs == {"가나", "다_"}


def test_align_encoded_length():
    assert align_encoded_length("日", "한", 2, 5) == (5, "日␀|␀", "한")
    assert align_encoded_length("日本", "한", 4, 2) == (4, "日本", "한␀")


def test_korean_name_format_policies():
    assert format_korean_name_prefer_given_leading_space("호조", "우지") == (
        "{호조}",
        "|_{우지}",
        2,
        3,
    )
    assert format_korean_name_without_added_space("이치조", "신류") == (
        "{이치}{조_}",
        "{신류}",
        4,
        2,
    )
    assert format_korean_name_without_added_space("혼간지", "코사") == (
        "{혼간}{지_}",
        "{코사}",
        4,
        2,
    )
