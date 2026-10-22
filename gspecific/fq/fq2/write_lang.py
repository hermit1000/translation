"""Write FQ2 PC-98 translations into copies of the original D88 disks.

Usage: python -m gspecific.fq.fq2.write_lang [workspace]
"""

import argparse
import json
from pathlib import Path
import re
import struct

from gspecific.fq.fq2.common import (
    DEFAULT_WORKSPACE, DISKS, digest, encoder, load_lang, read_at,
    sector_offsets, source_path, write_at,
)


def encode_name(text, words):
    codes = []
    cursor = 0
    for match in re.finditer(r"\{([^{}]+)\}", text):
        if match.start() != cursor:
            raise ValueError(f"name must use {{custom_word}} tokens: {text!r}")
        codes.append(bytes.fromhex(words[match.group(1)]))
        cursor = match.end()
    if cursor != len(text):
        raise ValueError(f"name must use {{custom_word}} tokens: {text!r}")
    return b"".join(codes)


def encode_dialogue(text, encode):
    """Drop a space immediately after 36 or 37 printed bytes in a 37-byte line."""
    output = bytearray()
    column = 0
    index = 0
    while index < len(text):
        if text[index] == "\x01":
            output.append(1)
            column = 0
            index += 1
            continue
        control = re.match(r"\\[WC][0-9]+", text[index:])
        if control:
            output.extend(control.group().encode("ascii"))
            index += len(control.group())
            continue
        char = text[index]
        if char == " " and column in (36, 37):
            column = 0
        else:
            raw = encode(char)
            output.extend(raw)
            column = len(raw) if column + len(raw) > 37 else column + len(raw)
        index += 1
    return bytes(output)


def patch_fixed(workspace, disk_name, source, output, sectors, encode, words):
    folder = workspace / "script-pc98" / disk_name
    paths = sorted(folder.glob("*_lang.json"),
                   key=lambda path: (path.name == "EXTRA_TEXT_lang.json", path.name))
    for path in paths:
        block = path.name.removesuffix("_lang.json")
        if block == "SERIFU":
            continue
        document = load_lang(workspace, disk_name, block, source)
        for number, entry in enumerate(document["entries"]):
            if entry["id"] != number:
                raise ValueError(f"entry order changed: {path}:{number}")
            translation = entry.get("translation")
            if not translation:
                continue
            start = entry["byte_offset_in_sector_stream"]
            original = bytes.fromhex(entry["source_hex"])
            if read_at(source, sectors, start, len(original)) != original:
                raise ValueError(f"original bytes differ: {path}:{number}")
            field_size = entry["field_byte_length"]
            raw = (encode_name(translation, words)
                   if block in ("UNIT_NAMES", "CLASS_NAMES") else encode(translation))
            if len(raw) >= field_size:
                raise ValueError(f"translation too long: {path}:{number}")
            if block == "UNIT_NAMES":
                field = raw.ljust(field_size, b"\0")
                locations = entry["locations"]
            elif block == "CLASS_NAMES":
                field = raw + b" " * (field_size - len(raw) - 1) + b"\0"
                locations = [start]
            else:
                padding = field_size - len(raw) - 1
                field = raw + b"\x81\x40" * (padding // 2) + b" " * (padding % 2) + b"\0"
                locations = [start]
            for location in locations:
                write_at(output, sectors, location, field)


def patch_dialogue(workspace, disk_name, source, output, sectors, encode):
    path = workspace / "script-pc98" / disk_name / "SERIFU_lang.json"
    if not path.exists():
        return
    document = load_lang(workspace, disk_name, "SERIFU", source)
    entries = document["entries"]
    count = len(entries)
    index_start = document["index_byte_offset_in_sector_stream"]
    old_pointers = struct.unpack(f"<{count}H", read_at(source, sectors, index_start, count * 2))
    if any(entry["id"] != number or
           entry["byte_offset_in_sector_stream"] != index_start + old_pointers[number]
           for number, entry in enumerate(entries)):
        raise ValueError(f"original dialogue pointers differ: {path}")
    text_start = index_start + min(old_pointers)
    text_end = index_start + old_pointers[-1] + len(entries[-1]["text"].encode("cp932")) + 1
    unique_pointers = sorted(set(old_pointers))
    raws = {}
    for number, (entry, pointer) in enumerate(zip(entries, old_pointers)):
        old_text = entry["text"].encode("cp932")
        if read_at(source, sectors, index_start + pointer, len(old_text)) != old_text:
            raise ValueError(f"original dialogue differs: {path}:{number}")
        terminator = read_at(source, sectors, index_start + pointer + len(old_text), 1)
        translation = entry.get("translation")
        raw = encode_dialogue(translation, encode) if translation else old_text
        if b"\0" in raw:
            raise ValueError(f"embedded NUL in dialogue: {path}:{number}")
        if terminator == b"\0":
            raw += b"\0"
        if pointer in raws and raws[pointer] != raw:
            raise ValueError(f"shared dialogue differs: {path}:{number}")
        raws[pointer] = raw
        if "shared_with_id" in entry and old_pointers[entry["shared_with_id"]] != pointer:
            raise ValueError(f"unexpected shared dialogue: {path}:{number}")
    relocated = {}
    contents = bytearray()
    for pointer in unique_pointers:
        relocated[pointer] = text_start + len(contents) - index_start
        contents.extend(raws[pointer])
    pointers = [relocated[pointer] for pointer in old_pointers]
    if text_start + len(contents) > text_end:
        raise ValueError(f"dialogue exceeds original space: {path}: "
                         f"{len(contents)} > {text_end - text_start}")
    write_at(output, sectors, index_start, struct.pack(f"<{count}H", *pointers))
    write_at(output, sectors, text_start,
             contents + b"\0" * (text_end - text_start - len(contents)))


def write_disks(workspace, output=None):
    output = output or workspace / "kor-pc98"
    code_root = Path(__file__).resolve().parents[3]
    encode = encoder(code_root, workspace)
    words = json.loads((workspace / "script-pc98/custom_word.json").read_text(encoding="utf-8"))
    prepared = []
    for disk_name in DISKS:
        original_path = source_path(workspace, disk_name)
        source = original_path.read_bytes()
        disk = bytearray(source)
        sectors = sector_offsets(source)
        patch_dialogue(workspace, disk_name, source, disk, sectors, encode)
        patch_fixed(workspace, disk_name, source, disk, sectors, encode, words)
        prepared.append((output / original_path.name, bytes(disk)))
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for path, disk in prepared:
        path.write_bytes(disk)
        results.append((path, digest(disk)))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--output", type=Path, help="directory for rebuilt D88 images")
    args = parser.parse_args()
    for path, sha256 in write_disks(args.workspace.resolve(), args.output):
        print(path, sha256)


if __name__ == "__main__":
    main()
