"""Shared D88 and FQ2 text helpers."""

import hashlib
import json
from pathlib import Path
import struct


DEFAULT_WORKSPACE = Path("C:/work_han/workspace12")
DISKS = {"Disk_Opening": "Opening disk", "Disk_A": "Disk A", "Disk_B": "Disk B"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_path(workspace, disk_name):
    return workspace / "jpn-pc98" / f"First Queen II - Sabaku no Joou ({DISKS[disk_name]}).d88"


def sector_offsets(data):
    tracks = struct.unpack_from("<164I", data, 0x20)
    sectors = {}
    for number, position in enumerate(tracks):
        if not position:
            continue
        end = next((offset for offset in tracks[number + 1:] if offset), len(data))
        while position < end:
            cylinder, head, sector, size_code = struct.unpack_from("<BBBB", data, position)
            size = struct.unpack_from("<H", data, position + 14)[0]
            if size_code != 1 or size != 256:
                raise ValueError("expected 256-byte D88 sectors")
            key = cylinder, head, sector
            if key in sectors:
                raise ValueError(f"duplicate D88 sector: {key}")
            sectors[key] = position + 16
            position += 16 + size
        if position != end:
            raise ValueError("invalid D88 track boundary")
    return [sectors[key] for key in sorted(sectors)]


def offsets(sectors, start, size):
    return [sectors[i // 256] + i % 256 for i in range(start, start + size)]


def read_at(data, sectors, start, size):
    return bytes(data[position] for position in offsets(sectors, start, size))


def write_at(data, sectors, start, value):
    for position, byte in zip(offsets(sectors, start, len(value)), value):
        data[position] = byte


def load_lang(workspace, disk_name, block, source):
    path = workspace / "script-pc98" / disk_name / f"{block}_lang.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    if document["source_sha256"] != digest(source):
        raise ValueError(f"source hash mismatch: {path}")
    if not document["format"].startswith("fq2-pc98-"):
        raise ValueError(f"unexpected format: {path}")
    return document


def encoder(code_root, workspace):
    table = json.loads((code_root / "font_table/font_table-kor-jin.json").read_text(encoding="utf-8"))
    words = json.loads((workspace / "script-pc98/custom_word.json").read_text(encoding="utf-8"))
    single = {glyph: bytes.fromhex(code) for code, glyph in table.items()}
    multi = sorted(((word.replace("_", " "), bytes.fromhex(code)) for word, code in words.items()),
                   key=lambda pair: len(pair[0]), reverse=True)

    def encode(value, use_words=False):
        result = bytearray()
        position = 0
        while position < len(value):
            if use_words:
                match = next(((word, raw) for word, raw in multi if value.startswith(word, position)), None)
                if match:
                    result.extend(match[1])
                    position += len(match[0])
                    continue
            char = value[position]
            if ord(char) < 128:
                result.append(ord(char))
            elif char == "\u3000":
                result.extend(b"\x81\x40")
            else:
                result.extend(single[char])
            position += 1
        return bytes(result)

    return encode
