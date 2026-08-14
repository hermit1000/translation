"""Apply NameDB names to the Nobunaga no Yabou 384 KB PC-98 scripts."""

import argparse
from pathlib import Path

from module.name_db import NameDB
from module.script import Script

from gspecific.nobu2.set_code_from_db_nobu2 import (
    calculate_modifications,
    print_modifications,
    save_modifications,
)


FILE_CONFIG = {
    "DATA17S.DAT": {
        "start": 0x01761,
        "end": 0x01992,
        "name_count": 17,
    },
    "DATA50S.DAT": {
        "start": 0x01761,
        "end": 0x01A46,
        "name_count": 53,
    },
    "ODAMAIN.EXE": {
        "start": 0x09A58,
        "end": 0x09C89,
        "name_count": 17,
    },
}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("c:/work_han/workspace0/script-pc98-384k"),
        help="directory containing the 384 KB *_jpn.json and *_kor.json files",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="write changes; without this option only print the planned changes",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    name_db = NameDB()
    game = "nb2"

    for file_name in FILE_CONFIG:
        jpn_path = args.base_dir / f"{file_name}_jpn.json"
        kor_path = args.base_dir / f"{file_name}_kor.json"
        script_jpn = Script(str(jpn_path))
        script_kor = Script(str(kor_path))

        mod_list_jpn, mod_list_kor, unknown_names = calculate_modifications(
            script_jpn,
            file_name,
            name_db,
            game,
            FILE_CONFIG,
        )
        print_modifications(
            file_name,
            mod_list_jpn,
            mod_list_kor,
            unknown_names,
            FILE_CONFIG,
        )

        if args.save:
            save_modifications(
                script_jpn,
                script_kor,
                str(jpn_path),
                str(kor_path),
                mod_list_jpn,
                mod_list_kor,
            )


if __name__ == "__main__":
    main()
