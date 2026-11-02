"""Disable FQ3 MAIN.EXE bold rendering."""

from __future__ import annotations

import struct

LOAD_BASE = 0x10000
CALL_SITE = 0x2538F
BITMAP_SITES = (0x25680, 0x256A6)
WRAPPER = 0x27AB4
CONTINUATION = 0x27593
BITMAP_HELPER = 0x21BA5
NAME_ROW_FORMAT = 0x2D32D
FIELD_CALL = 0x25819
FIELD_ROUTINE = 0x25758
OPEN_BOLD_SITES = (0x8ACE, 0x8B88, 0x8C87)
OPEN_BOLD_BRANCH = bytes.fromhex("2E F6 06 64 22 80 74")


def near_call(at: int, target: int) -> bytes:
    return b"\xE8" + struct.pack("<h", target - (at + 3))


def patch_image(image: bytes) -> bytes:
    output = bytearray(image)

    def replace(address: int, expected: bytes, replacement: bytes) -> None:
        if len(expected) != len(replacement):
            raise ValueError("render patch changes unpacked MAIN.EXE size")
        at = address - LOAD_BASE
        if output[at:at + len(expected)] != expected:
            raise ValueError(f"unexpected MAIN.EXE bytes at {address:05X}")
        output[at:at + len(expected)] = replacement

    # Force the CG path to use the thin bitmap helper for every glyph.
    call_at = WRAPPER + 4
    displacement = 0x25628 - (call_at + 3)
    wrapper = b"\x53\xBB\xFF\xFF\xE8" + struct.pack("<h", displacement) + b"\x5B\xC3\x90\x90\x90"
    replace(WRAPPER, b"\x00" * len(wrapper), wrapper)
    continuation = (b"\x19\xDB" + near_call(CONTINUATION + 2, 0x25628)
                    + b"\x5B\xC3" + b"\x90" * 6)
    replace(CONTINUATION, b"\x00" * len(continuation), continuation)
    bitmap_helper = b"\x86\xC4\x84\xDB\x75\x02\xD1\xE8\x86\xC4\xC3"
    replace(BITMAP_HELPER, b"\x00" * len(bitmap_helper), bitmap_helper)
    replace(CALL_SITE, near_call(CALL_SITE, 0x25628), near_call(CALL_SITE, WRAPPER))
    for address in BITMAP_SITES:
        replace(address, b"\x86\xC4\xD1\xE8\x86\xC4",
                near_call(address, BITMAP_HELPER) + b"\x90" * 3)

    # Mixed one- and two-byte names must advance by the declared field width.
    replace(NAME_ROW_FORMAT, b" \\AS \\8S", b"\\AS  \\8S")
    replace(FIELD_CALL, near_call(FIELD_CALL, FIELD_ROUTINE),
            near_call(FIELD_CALL, CONTINUATION))
    field_helper = (b"\x52" + near_call(CONTINUATION + 1, FIELD_ROUTINE)
                    + b"\x5A\x89\xE5\x8A\x46\x08\x00\xC6\xC3")
    replace(CONTINUATION, continuation, field_helper)

    return bytes(output)


def patch_open_exe(data: bytes) -> bytes:
    """Skip OPEN.EXE's three SHR+OR thickening blocks."""
    output = bytearray(data)
    if data.count(OPEN_BOLD_BRANCH) != len(OPEN_BOLD_SITES):
        raise ValueError("OPEN.EXE bold branch count changed")
    for at in OPEN_BOLD_SITES:
        if output[at:at + len(OPEN_BOLD_BRANCH)] != OPEN_BOLD_BRANCH:
            raise ValueError(f"unexpected OPEN.EXE bold branch at {at:05X}")
        output[at + len(OPEN_BOLD_BRANCH) - 1] = 0xEB  # JE -> JMP
    return bytes(output)
