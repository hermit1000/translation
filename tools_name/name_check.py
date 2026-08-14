from pathlib import Path
from typing import List, Optional, Tuple

from module.name_codec import clean_script_name
from module.name_db import NameDB
from module.script import Script
from rich.console import Console


GAME = "nb5"
WORKSPACE_NUMBER = 5
PLATFORM = "pc98"
FILE_NAMES = (
    "MAIN.EXE",
    *(f"S{index}T.NB5" for index in range(5)),
    *(f"SN{index}.NB5" for index in range(5)),
)
PERSON_NAME_RANGES = {
    "MAIN.EXE": (0x598C6, 0x5D794),
}


def get_workspace_script_dir(workspace_number: int, platform: str) -> Path:
    work_han_dir = Path(__file__).resolve().parents[2]
    return work_han_dir / f"workspace{workspace_number}" / f"script-{platform}"


def decode_name(
    name_db: NameDB,
    name_type: str,
    value: str,
    game: str,
    description: Optional[str] = None,
) -> Optional[str]:
    name = clean_script_name(value)
    if not name.startswith("0x:"):
        return name
    decoded_name = name_db.find_name_by_code(name_type, name, game)
    if decoded_name is not None:
        return decoded_name
    return description.strip() if description else None


def get_component_translation(database: dict, name: str):
    info = database.get(name)
    return "?" if info is None else info.get("kor", "?")


def print_missing_name(console: Console, name_db: NameDB, family: str, given: str) -> str:
    family_kor = get_component_translation(name_db.family_name_db, family)
    given_kor = get_component_translation(name_db.given_name_db, given)
    candidate = f"{family} {given} - {family_kor} {given_kor}"
    console.print(candidate)

    if family_kor == "?" and family in name_db.given_name_db:
        console.print("Warning: Family name is in the given name database.")
    if given_kor == "?" and given in name_db.family_name_db:
        console.print("Warning: Given name is in the family name database.")

    return candidate


def save_missing_candidates(output_path: Path, candidates: List[str]) -> None:
    text = "\n".join(candidates)
    if text:
        text += "\n"
    output_path.write_text(text, encoding="utf-8")


def update_game_from_script(
    script: Script,
    name_db: NameDB,
    game: str,
    console: Console,
    address_range: Optional[Tuple[int, int]] = None,
    missing_candidates: Optional[List[str]] = None,
) -> Tuple[int, int, int]:
    entries = list(script.script.items())
    if address_range is not None:
        range_start, range_end = address_range
        entries = [
            (address, content)
            for address, content in entries
            if range_start <= int(address.split("=")[0], 16) <= range_end
        ]

    if len(entries) % 2:
        raise ValueError(f"Unpaired name entry: {entries[-1][0]}")

    checked_count = 0
    updated_count = 0
    missing_count = 0

    for index in range(0, len(entries), 2):
        (family_address, family_content), (given_address, given_content) = entries[index : index + 2]

        family_end = int(family_address.split("=")[1], 16)
        given_start = int(given_address.split("=")[0], 16)
        address_gap = given_start - family_end
        if not 1 <= address_gap <= 8:
            raise ValueError(f"Family and given name addresses are not adjacent: {family_address}, {given_address}")

        family = decode_name(
            name_db,
            "family",
            family_content.text,
            game,
            family_content.description,
        )
        given = decode_name(
            name_db,
            "given",
            given_content.text,
            game,
            given_content.description,
        )
        if family is None or given is None:
            unresolved = family_content.text if family is None else given_content.text
            console.print(f"Unregistered name code: {unresolved}")
            missing_count += 1
            continue

        checked_count += 1
        full_name = f"{family} {given}"
        if name_db.get_full_name(full_name) is None:
            candidate = print_missing_name(console, name_db, family, given)
            if missing_candidates is not None:
                missing_candidates.append(candidate)
            missing_count += 1
            continue

        if name_db.add_game(full_name, game):
            console.print(f"Add game: {full_name}")
            updated_count += 1

    return checked_count, updated_count, missing_count


def main() -> None:
    console = Console()
    name_db = NameDB()
    base_dir = get_workspace_script_dir(WORKSPACE_NUMBER, PLATFORM)
    missing_candidates = []
    total_checked_count = 0
    total_updated_count = 0
    total_missing_count = 0

    for file_name in FILE_NAMES:
        script_path = base_dir / f"{file_name}_jpn.json"
        script = Script(str(script_path))
        checked_count, updated_count, missing_count = update_game_from_script(
            script,
            name_db,
            GAME,
            console,
            PERSON_NAME_RANGES.get(file_name.upper()),
            missing_candidates,
        )
        total_checked_count += checked_count
        total_updated_count += updated_count
        total_missing_count += missing_count
        console.print(
            f"{file_name}: checked {checked_count}, DB updated {updated_count}, missing or unresolved {missing_count}"
        )

    candidate_path = base_dir.parent / "ss.txt"
    save_missing_candidates(candidate_path, missing_candidates)

    # if updated_count:
    #     name_db.save_db()

    console.print(
        f"Checked: {total_checked_count}, DB updated: {total_updated_count}, "
        f"missing or unresolved: {total_missing_count}"
    )
    console.print(f"Saved missing candidates: {candidate_path}")


if __name__ == "__main__":
    main()
