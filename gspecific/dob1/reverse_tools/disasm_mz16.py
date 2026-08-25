#!/usr/bin/env python3
"""Linear 16-bit disassembly of an MZ load image."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_16, Cs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--raw", action="store_true", help="treat input as a raw 16-bit image")
    parser.add_argument("--offset", help="load-image offset in hexadecimal")
    parser.add_argument("--length", default="200", help="byte count in hexadecimal")
    args = parser.parse_args()

    data = args.input.read_bytes()
    if args.raw:
        header_size = 0
        ip = cs = 0
    else:
        header_size = struct.unpack_from("<H", data, 8)[0] * 16
        ip = struct.unpack_from("<H", data, 0x14)[0]
        cs = struct.unpack_from("<H", data, 0x16)[0]
    runtime_offset = int(args.offset, 16) if args.offset else cs * 16 + ip
    file_offset = header_size + runtime_offset
    length = int(args.length, 16)

    print(
        f"header=0x{header_size:X} entry={cs:04X}:{ip:04X} "
        f"runtime=0x{runtime_offset:04X} file=0x{file_offset:04X}"
    )
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    for insn in md.disasm(data[file_offset : file_offset + length], runtime_offset):
        raw = insn.bytes.hex(" ").upper()
        print(f"{insn.address:04X}  {raw:<24} {insn.mnemonic:<8} {insn.op_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
