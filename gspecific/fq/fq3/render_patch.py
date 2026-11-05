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
TITLE_LOAD_CLOSE_CALL = 0x22A46
TITLE_LOAD_FLAG_HELPER = 0x20A28
TITLE_LOAD_RELOAD_CHECK = 0x26DA8
SAVE_TIME_LABELS = (
    (0x22B37, 0x8E9E, 0x8F62),  # 時 -> 시
    (0x22B3D, 0x8AD4, 0x88A1),  # 間 -> 간
    (0x22B4E, 0x95AA, 0x8DCE),  # 分 -> 분
    (0x22B5F, 0x9562, 0x9269),  # 秒 -> 초
)
OPEN_BOLD_SITES = (0x8ACE, 0x8B88, 0x8C87)
OPEN_BOLD_BRANCH = bytes.fromhex("2E F6 06 64 22 80 74")
FIELD_NAME_CLIP = 0x25C65
BITMAP_COPY_START = 0x275A5
BITMAP_COPY_END = 0x275E6
NAME_CLIP_HELPER = BITMAP_COPY_START + 17
STATUS_COPY_START = BITMAP_COPY_END
STATUS_COPY_END = 0x27627
STATUS_NAME_WRAPPER = STATUS_COPY_START + 17
STATUS_ATTR_HELPER = STATUS_NAME_WRAPPER + 14
STATUS_NAME_PRINT = 0x25C70
DOUBLE_BYTE_ATTRIBUTE = 0x2598C


def near_call(at: int, target: int) -> bytes:
    return b"\xE8" + struct.pack("<h", target - (at + 3))


def name_clip_helper() -> bytes:
    """End the field status name at a complete character within three bytes."""
    code = bytearray(b"\x50\x53\x8B\x46\x00")  # save AX/BX; inspect byte 0
    code += near_call(NAME_CLIP_HELPER + len(code), 0x259DC)
    first_pair = len(code)
    code += b"\x73\x00"  # first character is two bytes
    code += b"\x8B\x46\x01"  # inspect byte 1
    code += near_call(NAME_CLIP_HELPER + len(code), 0x259DC)
    second_pair = len(code)
    code += b"\x73\x00"  # a one-byte + two-byte name fits
    third = len(code)
    code += b"\x8B\x46\x02"  # inspect byte 2
    code += near_call(NAME_CLIP_HELPER + len(code), 0x259DC)
    single_third = len(code)
    code += b"\x72\x00"
    code += b"\xC6\x46\x02\x00"  # incomplete pair: end after byte 1
    skip_single = len(code)
    code += b"\xEB\x00"
    keep_three = len(code)
    code += b"\xC6\x46\x03\x00"  # third byte is a complete character
    done = len(code)
    code += b"\x5B\x58\xC3"
    for branch, target in ((first_pair, third), (second_pair, keep_three),
                           (single_third, keep_three), (skip_single, done)):
        offset = target - (branch + 2)
        if not -128 <= offset <= 127:
            raise ValueError("name clip helper branch exceeds short range")
        code[branch + 1] = offset & 0xFF
    return bytes(code)


def status_attr_helper() -> bytes:
    """Use the single-byte background mode for status-name double-byte cells."""
    code = bytearray(b"\x80\xCA\x10")  # original OR DL,10h
    code += b"\xF6\x06\x75\x54\x80"  # status name is being drawn
    inactive = len(code)
    code += b"\x74\x00"
    code += b"\x80\xF2\x30"  # match the one-byte glyph background mode
    code += b"\xF7\xC7\x02\x00"  # second cell in a character pair
    first_cell = len(code)
    code += b"\x74\x00"
    code += b"\x80\xCA\x10"
    done = len(code)
    code += b"\xC3"
    code[inactive + 1] = done - (inactive + 2)
    code[first_cell + 1] = done - (first_cell + 2)
    return bytes(code)


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

    # Title loading originally decides whether to reload HITOBUF.DAT by
    # comparing the first saved unit-name byte with BE. Korean names use a
    # different byte. Record a successful load in the existing mode flag and
    # test that flag instead. INC preserves the close call's carry result.
    loaded_helper = (near_call(TITLE_LOAD_FLAG_HELPER, 0x27E9F)
                     + b"\xFE\x06\xAE\x4D\xC3")
    replace(TITLE_LOAD_FLAG_HELPER, b"\x00" * len(loaded_helper), loaded_helper)
    replace(TITLE_LOAD_CLOSE_CALL,
            near_call(TITLE_LOAD_CLOSE_CALL, 0x27E9F),
            near_call(TITLE_LOAD_CLOSE_CALL, TITLE_LOAD_FLAG_HELPER))
    replace(TITLE_LOAD_RELOAD_CHECK, b"\x36\x80\x3E\x00\x00\xBE",
            b"\x80\x3E\xAE\x4D\x02\x90")

    # The field status row displays three name bytes. Its original terminator
    # can split a two-byte character (for example, 아스콧: C7 C6 97 5B).
    # Compact the equivalent 16-row bitmap copy to make room for a boundary
    # check; the original name word is already restored after drawing.
    original_copy = b"\xA5\x83\xC7\x4E" * 15 + b"\xA5\x81\xEF\xB2\x84"
    compact_copy = b"\x51\xB9\x10\x00\xA5\x83\xC7\x4E\xE2\xFA\x81\xEF\x00\x85\x59"
    helper = name_clip_helper()
    available = BITMAP_COPY_END - NAME_CLIP_HELPER
    if len(helper) > available:
        raise ValueError("name clip helper exceeds bitmap copy space")
    replacement = compact_copy + bytes((0xEB, available)) + helper
    replacement += b"\x90" * (BITMAP_COPY_END - BITMAP_COPY_START - len(replacement))
    replace(BITMAP_COPY_START, original_copy, replacement)
    replace(FIELD_NAME_CLIP, b"\xC6\x46\x03\x00",
            near_call(FIELD_NAME_CLIP, NAME_CLIP_HELPER) + b"\x90")

    # The 2-byte renderer uses background mode 10h even on the green field
    # status bar. Mark only the status-name call and give its glyphs the same
    # 20h/30h background mode that 1-byte glyphs already receive there.
    status_wrapper = (b"\x80\x0E\x75\x54\x80"
                      + near_call(STATUS_NAME_WRAPPER + 5, 0x25733)
                      + b"\x80\x26\x75\x54\x7F\xC3")
    if len(status_wrapper) != STATUS_ATTR_HELPER - STATUS_NAME_WRAPPER:
        raise ValueError("unexpected field status wrapper length")
    status_code = status_wrapper + status_attr_helper()
    status_available = STATUS_COPY_END - STATUS_NAME_WRAPPER
    if len(status_code) > status_available:
        raise ValueError("field status helpers exceed bitmap copy space")
    status_replacement = compact_copy + bytes((0xEB, status_available)) + status_code
    status_replacement += b"\x90" * (STATUS_COPY_END - STATUS_COPY_START
                                      - len(status_replacement))
    replace(STATUS_COPY_START, original_copy, status_replacement)
    replace(STATUS_NAME_PRINT, near_call(STATUS_NAME_PRINT, 0x25733),
            near_call(STATUS_NAME_PRINT, STATUS_NAME_WRAPPER))
    replace(DOUBLE_BYTE_ATTRIBUTE, b"\x80\xCA\x10",
            near_call(DOUBLE_BYTE_ATTRIBUTE, STATUS_ATTR_HELPER))

    # Save-slot time labels are embedded in code rather than script JSON.
    for address, japanese, korean in SAVE_TIME_LABELS:
        replace(address, b"\xB8" + japanese.to_bytes(2, "little"),
                b"\xB8" + korean.to_bytes(2, "little"))

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
