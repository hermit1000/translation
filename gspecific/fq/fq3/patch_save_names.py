"""Update FQ3 save-file unit names from the rebuilt HITOBUF.DAT.

Run: python patch_save_names.py [workspace] [--check]
Original saves are copied to the workspace backup/save-backups folder before modification.
"""

from __future__ import annotations

import argparse
from pathlib import Path


WORKSPACE_PATH = Path(r"C:\work_han\workspace13")
NAME_BLOCK = 0x480
RECORD_SIZE = 32
NAME_SIZE = 10
RECORD_COUNT = 640
SAVE_SIZE = 29824


def patch(workspace: Path, check: bool = False) -> None:
    original = (workspace / "jpn-pc98" / "HITOBUF.DAT").read_bytes()
    korean = (workspace / "kor-pc98" / "HITOBUF.DAT").read_bytes()
    if len(original) != RECORD_COUNT * RECORD_SIZE + 1 or len(korean) != len(original):
        raise ValueError("unexpected HITOBUF.DAT structure")
    save_dir = workspace / "kor-pc98-dosbox-x"
    paths = [save_dir / f"FQ3-SD.{slot:02d}" for slot in range(6)]
    prepared: list[tuple[Path, bytes, bytes, int]] = []
    for path in paths:
        source = path.read_bytes()
        if len(source) != SAVE_SIZE:
            raise ValueError(f"unexpected save size: {path}: {len(source)}")
        output = bytearray(source)
        changed = 0
        for index in range(RECORD_COUNT):
            source_at = index * RECORD_SIZE
            save_at = NAME_BLOCK + source_at
            japanese_name = original[source_at:source_at + NAME_SIZE]
            korean_name = korean[source_at:source_at + NAME_SIZE]
            current = source[save_at:save_at + NAME_SIZE]
            if current not in (japanese_name, korean_name):
                raise ValueError(f"save contains a separately edited name: {path}, unit {index}")
            if current != korean_name:
                output[save_at:save_at + NAME_SIZE] = korean_name
                changed += 1
        prepared.append((path, source, bytes(output), changed))
    backup_dir = workspace / "backup" / "save-backups"
    for path, source, output, changed in prepared:
        if not check and changed:
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / path.name
            if not backup.exists():
                backup.write_bytes(source)
            path.write_bytes(output)
        print(f"{path}: {changed} unit names updated")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=WORKSPACE_PATH)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()
    patch(args.workspace.resolve(), args.check)


if __name__ == "__main__":
    main()
