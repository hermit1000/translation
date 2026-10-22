"""Write FQ1 PC-98 *_lang.json translations into original D88 disk images.

Usage: python -m gspecific.fq.fq1.write_lang [workspace]
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from module import jisx0201


jisx0201_table = jisx0201.jisx0201_table
DEFAULT_WORKSPACE = Path("C:/work_han/workspace11")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoder(code_root):
    table = json.loads((code_root / "font_table/font_table-kor-jin.json").read_text(encoding="utf-8"))
    full = {}
    for code, glyph in table.items():
        full.setdefault(glyph, bytes.fromhex(code))
    half = {glyph: bytes.fromhex(code) for code, glyph in jisx0201_table.items()}
    half.update({"\\": b"\\", "~": b"~"})

    def encode(text):
        out = bytearray()
        index = 0
        while index < len(text):
            char = text[index]
            if char == "|":
                assert index + 1 < len(text), "dangling |"
                next_char = text[index + 1]
                out += b"\0" if next_char == "␀" else half[next_char]
                index += 2
            elif char == "_":
                out += b"\x81\x40"
                index += 1
            elif char == "␀":
                out += b"\0\0"
                index += 1
            else:
                assert char != " ", f"use _ or |_ for spaces (character {index + 1})"
                out += full[char]
                index += 1
        return bytes(out)

    return encode


def sectors_in_stream(disk):
    tracks = struct.unpack_from("<164I", disk, 0x20)
    sectors = {}
    for track, position in enumerate(tracks):
        if not position:
            continue
        end = next((offset for offset in tracks[track + 1:] if offset), len(disk))
        while position < end:
            cylinder, head, sector, size_code = struct.unpack_from("<BBBB", disk, position)
            size = struct.unpack_from("<H", disk, position + 14)[0]
            assert size_code == 1 and size == 256
            key = cylinder, head, sector
            assert key not in sectors
            sectors[key] = position + 16
            position += 16 + size
        assert position == end
    keys = sorted(sectors)
    assert len(keys) == 4056
    return [sectors[key] for key in keys]


def positions(sectors, start, size):
    return [sectors[i // 256] + i % 256 for i in range(start, start + size)]


def read_at(disk, offsets):
    return bytes(disk[offset] for offset in offsets)


def write_at(disk, offsets, raw):
    assert len(offsets) == len(raw)
    for offset, value in zip(offsets, raw):
        disk[offset] = value


def language(workspace, letter, name, source):
    path = workspace / f"script-pc98/Disk_{letter}/{name}_lang.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["source_sha256"] == digest(source), path
    return data


def encode_entry(encode, path, entry, text=None):
    if text is None:
        text = entry["translation"]
    try:
        return encode(text)
    except (AssertionError, KeyError) as exc:
        marker = f'"id": {entry["id"]}'
        line = next((number for number, content in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
                     if marker in content), None)
        raise ValueError(f"\nJSON file: {path}:{line}\nEntry ID: {entry['id']}"
                         f"\nTranslation: {text!r}\nReason: {exc}") from exc


def strip_serifu_wrap_spaces(text):
    while True:
        result = []
        cell = 0
        index = 0
        while index < len(text):
            token = text[index:index + 2] if text[index] == "|" else text[index]
            if not (cell and cell % 18 == 0 and token in ("_", "|_")):
                result.append(token)
            cell += 1
            index += len(token)
        updated = "".join(result)
        if updated == text:
            return updated
        text = updated


def patch_dialogue(workspace, letter, source, disk, sectors, encode):
    data = language(workspace, letter, "SERIFU", source)
    entries = data["entries"]
    assert [entry["id"] for entry in entries] == list(range(len(entries)))
    index_start = data["index_byte_offset_in_sector_stream"]
    text_start = index_start + 512
    assert entries[0]["byte_offset_in_sector_stream"] == text_start
    original = [entry["text"].encode("cp932") + b"\0" for entry in entries]
    original_length = sum(map(len, original))
    assert read_at(source, positions(sectors, text_start, original_length)) == b"".join(original)
    old_offsets = struct.unpack("<256H", read_at(source, positions(sectors, index_start, 512)))
    assert tuple(old_offsets[:len(entries)]) == tuple(entry["byte_offset_in_sector_stream"] - text_start for entry in entries)
    assert not any(old_offsets[len(entries):])
    path = workspace / f"script-pc98/Disk_{letter}/SERIFU_lang.json"
    encoded = [encode_entry(encode, path, entry, strip_serifu_wrap_spaces(entry["translation"])) + b"\0" if "translation" in entry else original[i]
               for i, entry in enumerate(entries)]
    assert all(raw.endswith(b"\0") and b"\0" not in raw[:-1] for raw in encoded)
    offsets = []
    cursor = 0
    for raw in encoded:
        offsets.append(cursor)
        cursor += len(raw)
    assert cursor <= original_length, (letter, cursor, original_length)
    index = struct.pack("<256H", *(offsets + [0] * (256 - len(offsets))))
    write_at(disk, positions(sectors, index_start, 512), index)
    write_at(disk, positions(sectors, text_start, original_length),
             b"".join(encoded) + b"\0" * (original_length - cursor))


def patch_fixed(workspace, source, disk, sectors, encode):
    for name in ("OPENING", "ENDING", "OPENING_EXTRA", "SYSTEM"):
        data = language(workspace, "A", name, source)
        for entry in data["entries"]:
            if not entry.get("translation"):
                continue
            old = entry["text"].encode("cp932")
            raw = encode_entry(encode, workspace / f"script-pc98/Disk_A/{name}_lang.json", entry)
            assert len(raw) <= len(old) == entry["byte_length"], (name, entry["id"])
            start = entry["byte_offset_in_sector_stream"]
            offsets = positions(sectors, start, len(old) + 1)
            assert read_at(source, offsets) == old + b"\0", (name, entry["id"])
            padding = len(old) - len(raw)
            write_at(disk, offsets, raw + b"\x81\x40" * (padding // 2) + b" " * (padding % 2) + b"\0")


def patch_unit_names(workspace, source, disk, encode):
    data = language(workspace, "B", "UNIT_NAMES", source)
    for entry in data["entries"]:
        if "translation" not in entry:
            continue
        old = encode(entry["text"])
        raw = encode_entry(encode, workspace / "script-pc98/Disk_B/UNIT_NAMES_lang.json", entry)
        assert len(old) <= 10 and 0 < len(raw) <= 10
        for location in entry["locations"]:
            offset = location["disk_byte_offset"]
            assert source[offset:offset + 10] == old + b"\0" * (10 - len(old))
            disk[offset:offset + 10] = raw + b"\0" * (10 - len(raw))


def patch_class_names(workspace, source, disk, encode):
    data = language(workspace, "A", "CLASS_NAMES", source)
    for entry in data["entries"]:
        offset = entry["disk_byte_offset"]
        old = encode(entry["text"])
        raw = encode_entry(encode, workspace / "script-pc98/Disk_A/CLASS_NAMES_lang.json", entry)
        assert len(old) == len(raw) == entry["field_byte_length"] == 9
        assert source[offset:offset + 9] == old
        disk[offset:offset + 9] = raw


def patch_locations(workspace, source, disk, sectors, encode):
    data = language(workspace, "A", "LOCATIONS", source)
    for entry in data["entries"]:
        if not entry.get("translation"):
            continue
        offsets = positions(sectors, entry["byte_offset_in_sector_stream"], 19)
        assert read_at(source, offsets) == bytes.fromhex(entry["source_hex"])
        raw = encode_entry(encode, workspace / "script-pc98/Disk_A/LOCATIONS_lang.json", entry)
        assert 0 < len(raw) <= entry["byte_length"] == 18, entry["id"]
        write_at(disk, offsets, raw + b" " * (18 - len(raw)) + b"\0")


def patch_item_names(workspace, source, disk, sectors, encode):
    data = language(workspace, "A", "ITEM_NAMES", source)
    path = workspace / "script-pc98/Disk_A/ITEM_NAMES_lang.json"
    entries = data["entries"]
    index_start = 64622
    text_start = entries[0]["byte_offset_in_sector_stream"]
    assert text_start == 64690 and len(entries) == 30
    original = []
    encoded = []
    for entry in entries:
        old = bytes.fromhex(entry["source_hex"])
        offsets = positions(sectors, entry["byte_offset_in_sector_stream"], len(old))
        assert read_at(source, offsets) == old, (path, entry["id"])
        original.append(old)
        encoded.append(encode_entry(encode, path, entry) + b"\0" if entry.get("translation") else old)
    assert b"".join(original) == read_at(source, positions(sectors, text_start, sum(map(len, original))))
    pointer_base = text_start - struct.unpack("<H", read_at(source, positions(sectors, index_start, 2)))[0]
    assert pointer_base == 13056
    old_pointers = struct.unpack("<30H", read_at(source, positions(sectors, index_start, 60)))
    assert all(pointer + pointer_base == entry["byte_offset_in_sector_stream"]
               for pointer, entry in zip(old_pointers, entries))
    cursor = text_start
    pointers = []
    for raw in encoded:
        pointers.append(cursor - pointer_base)
        cursor += len(raw)
    original_end = text_start + sum(map(len, original))
    assert cursor <= original_end, (path, cursor - text_start, original_end - text_start)
    write_at(disk, positions(sectors, index_start, 60), struct.pack("<30H", *pointers))
    write_at(disk, positions(sectors, text_start, original_end - text_start),
             b"".join(encoded) + b"\0" * (original_end - cursor))


def patch_serifu_extra(workspace, source, disk, sectors, encode):
    data = language(workspace, "A", "SERIFU_EXTRA", source)
    path = workspace / "script-pc98/Disk_A/SERIFU_EXTRA_lang.json"
    for entry in data["entries"]:
        if not entry.get("translation"):
            continue
        old = entry["text"].encode("cp932")
        assert len(old) == entry["byte_length"], (path, entry["id"])
        offsets = positions(sectors, entry["byte_offset_in_sector_stream"], len(old))
        assert read_at(source, offsets) == old, (path, entry["id"])
        raw = encode_entry(encode, path, entry)
        assert len(raw) <= len(old), (path, entry["id"], len(raw), len(old))
        padding = len(old) - len(raw)
        write_at(disk, offsets, raw + b"\x81\x40" * (padding // 2) + b" " * (padding % 2))


def update_translation_lengths(workspace, encode):
    for path in sorted((workspace / "script-pc98").rglob("*_lang.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for entry in data["entries"]:
            if not entry.get("translation"):
                continue
            translation = entry["translation"]
            if path.name == "SERIFU_lang.json" and path.parent.name in ("Disk_A", "Disk_B"):
                translation = strip_serifu_wrap_spaces(translation)
            length = len(encode_entry(encode, path, entry, translation))
            if entry.get("translation_byte_length") != length:
                entry["translation_byte_length"] = length
                changed = True
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\r\n")
            print(path, "translation lengths updated")


def write_disks(workspace, code_root):
    encode = encoder(code_root)
    output = workspace / "kor-pc98"
    output.mkdir(exist_ok=True)
    for letter in "AB":
        source_path = workspace / f"jpn-pc98/First Queen (Disk {letter}).d88"
        source = source_path.read_bytes()
        disk = bytearray(source)
        sectors = sectors_in_stream(source)
        patch_dialogue(workspace, letter, source, disk, sectors, encode)
        if letter == "A":
            patch_fixed(workspace, source, disk, sectors, encode)
            patch_class_names(workspace, source, disk, encode)
            patch_locations(workspace, source, disk, sectors, encode)
            patch_item_names(workspace, source, disk, sectors, encode)
            patch_serifu_extra(workspace, source, disk, sectors, encode)
        else:
            patch_unit_names(workspace, source, disk, encode)
        target = output / source_path.name
        target.write_bytes(disk)
        print(target, digest(disk))
    update_translation_lengths(workspace, encode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=DEFAULT_WORKSPACE)
    args = parser.parse_args()
    write_disks(args.workspace.resolve(), Path(jisx0201.__file__).resolve().parents[1])


if __name__ == "__main__":
    main()
