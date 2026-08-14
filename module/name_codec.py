from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class NamePair:
    family: str
    given: str

    @classmethod
    def parse(cls, value: str) -> NamePair:
        parts = value.split(" ")
        if len(parts) != 2 or not all(parts):
            raise ValueError(f"Name must contain exactly one family and given name: {value!r}")
        return cls(family=parts[0], given=parts[1])

    def __str__(self) -> str:
        return f"{self.family} {self.given}"


def clean_script_name(name: str) -> str:
    return name.replace("|_", "").replace("|␀", "").replace("␀", "")


def pair_korean(text: str) -> str:
    return "".join(f"{{{text[i:i + 2]}}}" for i in range(0, len(text), 2))


def split_pairs(text: str, padding: str = "_") -> Tuple[List[str], bool]:
    pairs = []
    padded = False
    for i in range(0, len(text), 2):
        pair = text[i : i + 2]
        if len(pair) == 1:
            pair += padding
            padded = True
        if " " in pair:
            raise ValueError(f"Name contains a space: {text!r}")
        pairs.append(pair)
    return pairs, padded


def align_encoded_length(
    source: str,
    target: str,
    source_length: int,
    target_length: int,
) -> Tuple[int, str, str]:
    length = source_length
    difference = target_length - source_length
    if difference > 0:
        source += "␀" * (difference // 2)
        if difference % 2:
            source += "|␀"
        length = target_length
    elif difference < 0:
        difference = -difference
        target += "␀" * (difference // 2)
        if difference % 2:
            target += "|␀"
    return length, source, target


def format_korean_name_prefer_given_leading_space(
    family: str,
    given: str,
    max_length: int = 6,
) -> Tuple[str, str, int, int]:
    full_name = f"{family} {given}"

    if len(family) % 2:
        family += "_"
    family_length = len(family)
    family_code = pair_korean(family)

    if len(given) % 2:
        given = "_" + given
        given_length = len(given)
        given_code = pair_korean(given)
        given_has_leading_space = True
    elif len(given) + 1 <= max_length:
        given_length = len(given) + 1
        given_code = "|_" + pair_korean(given)
        given_has_leading_space = True
    else:
        given_length = len(given)
        given_code = pair_korean(given)
        given_has_leading_space = False

    if not given_has_leading_space:
        if not family.endswith("_") and family_length + 1 <= max_length:
            family_code += "|_"
            family_length += 1
        elif not family.endswith("_"):
            raise ValueError(f"Name length is too long: {full_name} ({family_length}/{given_length} bytes)")

    if family_length > max_length or given_length > max_length:
        raise ValueError(f"Name length is too long: {full_name} ({family_length}/{given_length} bytes)")

    return family_code, given_code, family_length, given_length


def format_korean_name_without_added_space(
    family: str,
    given: str,
    family_max_length: int = 6,
    given_max_length: int = 4,
) -> Tuple[str, str, int, int]:
    full_name = f"{family} {given}"

    family_pairs, _ = split_pairs(family)
    family_code = "".join(f"{{{pair}}}" for pair in family_pairs)
    family_length = len(family_pairs) * 2

    given_pairs, _ = split_pairs(given)
    given_code = "".join(f"{{{pair}}}" for pair in given_pairs)
    given_length = len(given_pairs) * 2

    if family_length > family_max_length or given_length > given_max_length:
        raise ValueError(f"Name length is too long: {full_name} ({family_length}/{given_length} bytes)")

    return family_code, given_code, family_length, given_length
