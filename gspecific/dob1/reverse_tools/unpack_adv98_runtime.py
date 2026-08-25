#!/usr/bin/env python3
"""Run an ADV98 self-extractor and dump its unpacked 64 KiB load segment."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_INTR, UC_MODE_16, Uc
from unicorn.x86_const import (
    UC_X86_REG_CS,
    UC_X86_REG_DS,
    UC_X86_REG_ES,
    UC_X86_REG_IP,
    UC_X86_REG_SP,
    UC_X86_REG_SS,
)


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, help="unpacked 64 KiB raw image")
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args()

    exe = args.input.read_bytes()
    if exe[:2] != b"MZ":
        raise ValueError("input is not an MZ executable")
    header_size = u16(exe, 8) * 16
    image = exe[header_size:]

    load_segment = 0x2000
    psp_segment = load_segment - 0x10
    start_cs = load_segment + u16(exe, 0x16)
    start_ip = u16(exe, 0x14)
    start_ss = load_segment + u16(exe, 0x0E)
    start_sp = u16(exe, 0x10)

    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, 0x100000)
    uc.mem_write(load_segment << 4, image)
    uc.reg_write(UC_X86_REG_CS, start_cs)
    uc.reg_write(UC_X86_REG_IP, start_ip)
    uc.reg_write(UC_X86_REG_SS, start_ss)
    uc.reg_write(UC_X86_REG_SP, start_sp)
    uc.reg_write(UC_X86_REG_DS, psp_segment)
    uc.reg_write(UC_X86_REG_ES, psp_segment)

    state: dict[str, int | bool] = {"far_jump_seen": False, "instructions": 0}

    def on_code(machine: Uc, address: int, size: int, _user: object) -> None:
        state["instructions"] = int(state["instructions"]) + 1
        if state["far_jump_seen"]:
            state["target_cs"] = machine.reg_read(UC_X86_REG_CS)
            state["target_ip"] = machine.reg_read(UC_X86_REG_IP)
            machine.emu_stop()
            return
        if bytes(machine.mem_read(address, 3)) == b"\x2e\xff\x2f":
            state["far_jump_seen"] = True

    def on_interrupt(_machine: Uc, number: int, _user: object) -> None:
        raise RuntimeError(f"unexpected interrupt 0x{number:02X} during unpacking")

    uc.hook_add(UC_HOOK_CODE, on_code)
    uc.hook_add(UC_HOOK_INTR, on_interrupt)
    uc.emu_start((start_cs << 4) + start_ip, 0, count=2_000_000)

    if not state["far_jump_seen"] or "target_cs" not in state:
        raise RuntimeError("self-extractor did not reach its final far jump")

    raw = bytes(uc.mem_read(load_segment << 4, 0x10000))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(raw)

    metadata = {
        "source": str(args.input.resolve()),
        "output": str(args.output.resolve()),
        "load_segment": f"{load_segment:04X}",
        "entry_before_unpack": f"{start_cs - load_segment:04X}:{start_ip:04X}",
        "entry_after_unpack": (
            f"{int(state['target_cs']) - load_segment:04X}:{int(state['target_ip']):04X}"
        ),
        "instruction_count": state["instructions"],
        "raw_size": len(raw),
    }
    metadata_path = args.metadata or args.output.with_suffix(args.output.suffix + ".json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
