"""Extract FQ1 PC-98 original text to script_init-pc98.

Usage: python -m gspecific.fq.fq1.extract_lang [workspace]
"""

import argparse
import json
from pathlib import Path
import struct

from gspecific.fq.fq1.write_lang import digest, positions, read_at, sectors_in_stream


DEFAULT_WORKSPACE = Path("C:/work_han/workspace11")
FIXED_BLOCKS = (
    ("OPENING", 3862, 5129, 37, "fq1-pc98-opening-text-v1"),
    ("ENDING", 5129, 5728, 23, "fq1-pc98-ending-text-v1"),
    ("OPENING_EXTRA", 5728, 5994, 10, "fq1-pc98-opening-extra-text-v1"),
    ("SYSTEM", 64998, 65861, 37, "fq1-pc98-system-messages-v1"),
    ("ITEM_NAMES", 64690, 64998, 30, "fq1-pc98-item-names-v1"),
)
EXTRA_FIELDS = (
    (843791, 36), (843834, 16), (843867, 36), (843910, 36),
    (843953, 36), (843996, 36), (844039, 16), (844081, 36),
    (844124, 36), (844167, 36), (844210, 12), (844239, 34),
    (844299, 36), (844342, 36), (844385, 32), (844431, 22),
    (844459, 36), (844525, 20),
)


def sector(sectors, disk, offset):
    cylinder, head, number = struct.unpack_from("<BBB", disk, sectors[offset // 256] - 16)
    return {"cylinder": cylinder, "head": head, "sector": number,
            "byte_offset": offset % 256}


def document(source_path, source, fmt, entries, **metadata):
    return {"format": fmt, "source": source_path,
            "source_sha256": digest(source), **metadata, "entries": entries}


def fixed_block(name, start, end, count, fmt, stream, sectors, disk, source_path):
    entries = []
    cursor = start
    while cursor < end:
        terminator = stream.index(b"\0", cursor, end)
        raw = stream[cursor:terminator]
        entry = {"id": len(entries), "text": raw.decode("cp932"),
                 "byte_offset_in_sector_stream": cursor, "byte_length": len(raw)}
        if name in ("OPENING", "ENDING", "OPENING_EXTRA"):
            entry["sector"] = sector(sectors, disk, cursor)
        if name == "ITEM_NAMES":
            entry.update(source_hex=(raw + b"\0").hex().upper(),
                         translation="", translation_byte_length=None)
        entries.append(entry)
        cursor = terminator + 1
    assert cursor == end and len(entries) == count, name
    metadata = {"sector_stream_start": start, "sector_stream_end_exclusive": end}
    if name in ("SYSTEM", "ITEM_NAMES"):
        metadata = {}
    return document(source_path, disk, fmt, entries, **metadata)


def locations(stream, disk, source_path):
    entries = []
    for number in range(55):
        offset = 63577 + number * 19
        raw = stream[offset:offset + 19]
        assert raw[-1] == 0
        entries.append({"id": number, "text": raw[:-1].decode("cp932").rstrip(" \u3000"),
                        "byte_offset_in_sector_stream": offset, "byte_length": 18,
                        "source_hex": raw.hex().upper(), "translation": "",
                        "translation_byte_length": None})
    return document(source_path, disk, "fq1-pc98-location-names-v1", entries)


def dialogue(letter, stream, sectors, disk, source_path):
    index_start, count = {"A": (825344, 195), "B": (931840, 185)}[letter]
    offsets = struct.unpack_from("<256H", stream, index_start)
    assert offsets[0] == 0 and not any(offsets[count:])
    assert all(offsets[i] < offsets[i + 1] for i in range(count - 1))
    text_start = index_start + 512
    entries = []
    for number in range(count):
        start = text_start + offsets[number]
        end = text_start + offsets[number + 1] if number + 1 < count else stream.index(b"\0", start) + 1
        assert stream[end - 1] == 0
        entries.append({"id": number, "text": stream[start:end - 1].decode("cp932"),
                        "byte_offset_in_sector_stream": start,
                        "sector": sector(sectors, disk, start)})
    return document(source_path, disk, "fq1-pc98-indexed-dialogue-v1", entries,
                    logical_block="SERIFU", index_byte_offset_in_sector_stream=index_start,
                    sector_stream_order="cylinder, head, sector")


def extra_dialogue(stream, sectors, disk, source_path):
    entries = []
    for offset, length in EXTRA_FIELDS:
        raw = stream[offset:offset + length]
        entries.append({"id": len(entries), "text": raw.decode("cp932"),
                        "byte_offset_in_sector_stream": offset, "byte_length": length,
                        "sector": sector(sectors, disk, offset),
                        "translation": "", "translation_byte_length": None})
    assert len(entries) == 18
    return document(source_path, disk, "fq1-pc98-extra-dialogue-fragments-v1", entries)


def extract(workspace):
    for letter in "AB":
        source_path = f"jpn-pc98/First Queen (Disk {letter}).d88"
        disk = (workspace / source_path).read_bytes()
        sectors = sectors_in_stream(disk)
        stream = b"".join(disk[offset:offset + 256] for offset in sectors)
        documents = {"SERIFU": dialogue(letter, stream, sectors, disk, source_path)}
        if letter == "A":
            for name, start, end, count, fmt in FIXED_BLOCKS:
                documents[name] = fixed_block(name, start, end, count, fmt,
                                              stream, sectors, disk, source_path)
            documents["LOCATIONS"] = locations(stream, disk, source_path)
            documents["SERIFU_EXTRA"] = extra_dialogue(stream, sectors, disk, source_path)
        output_dir = workspace / f"script_init-pc98/Disk_{letter}"
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, data in documents.items():
            output = output_dir / f"{name}_jpn.json"
            output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8", newline="\r\n")
            print(output, len(data["entries"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=DEFAULT_WORKSPACE)
    args = parser.parse_args()
    extract(args.workspace.resolve())


if __name__ == "__main__":
    main()
