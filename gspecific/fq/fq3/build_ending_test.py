"""Build an isolated PC-98 FQ3 copy that enters END.BIN after initialization."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from gspecific.fq.fq3.repack_main import repack
from gspecific.fq.fq3.unpack_main import unpack, word

PATCH_OFFSET = 0xBB0D
ORIGINAL = bytes.fromhex("80 3E C4 00 00 74 03")
PATCHED = bytes.fromhex("C6 06 C4 00 FF 90 90")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(r"C:\work_han\workspace13"))
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    source = workspace / "kor-pc98-dosbox-x"
    target = workspace / "ending-test-pc98"
    main_exe = (source / "MAIN.EXE").read_bytes()
    unpacked, image = unpack(main_exe)
    header_size = word(unpacked, 8) * 16
    patched = bytearray(unpacked)
    if patched[PATCH_OFFSET:PATCH_OFFSET + len(ORIGINAL)] != ORIGINAL:
        raise ValueError("MAIN.EXE ending trigger does not match the verified version")
    patched[PATCH_OFFSET:PATCH_OFFSET + len(PATCHED)] = PATCHED

    config_path = workspace / "fq3-kor.conf"
    if not config_path.exists():
        config_path = workspace / "FirstQueen-kor.conf"
    original_conf = config_path.read_bytes()
    old_mount = b"mount a kor-pc98-dosbox-x"
    if original_conf.count(old_mount) != 1:
        raise ValueError("unexpected DOSBox-X mount configuration")
    ending_conf = original_conf.replace(old_mount, b"mount a ending-test-pc98")

    new_target = not target.exists()
    if new_target:
        shutil.copytree(source, target)
    elif not target.is_dir() or not (target / "MAIN.EXE").is_file():
        raise ValueError(f"unexpected ending test directory: {target}")
    for name in ("FQ3MES.DAT", "HITOBUF.DAT", "OPEN.EXE", "END.BIN", "GDATA.CHR"):
        shutil.copyfile(source / name, target / name)
    (target / "MAIN.EXE").write_bytes(repack(main_exe, patched[header_size:]))
    if new_target:
        (workspace / "FirstQueen-ending.conf").write_bytes(ending_conf)
        (workspace / "FirstQueen-ending.bat").write_bytes(
            b'@echo off\r\ncd /d "%~dp0"\r\n'
            b'start "" "C:\\DOSBox-X\\dosbox-x.exe" -noconsole -conf "FirstQueen-ending.conf"\r\n'
        )
    print(f"Updated {target / 'MAIN.EXE'}")
    print(f"Patched MAIN.EXE at {PATCH_OFFSET:05X}: {ORIGINAL.hex()} -> {PATCHED.hex()}")
    print(f"Launch with {workspace / 'FirstQueen-ending.bat'}")


if __name__ == "__main__":
    main()
