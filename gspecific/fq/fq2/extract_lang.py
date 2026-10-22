"""Verify FQ2 source locations and create translation-free extraction JSON.

Usage: python -m gspecific.fq.fq2.extract_lang [workspace]
"""

import argparse
import json
from pathlib import Path

from gspecific.fq.fq2.common import (
    DEFAULT_WORKSPACE, DISKS, load_lang, read_at, sector_offsets, source_path,
)


def extract(workspace):
    for disk_name in DISKS:
        source = source_path(workspace, disk_name).read_bytes()
        sectors = sector_offsets(source)
        output_dir = workspace / "script_init-pc98" / disk_name
        output_dir.mkdir(parents=True, exist_ok=True)
        for language in sorted((workspace / "script-pc98" / disk_name).glob("*_lang.json")):
            block = language.name.removesuffix("_lang.json")
            document = load_lang(workspace, disk_name, block, source)
            for entry in document["entries"]:
                if "source_hex" in entry:
                    actual = read_at(source, sectors, entry["byte_offset_in_sector_stream"],
                                     len(bytes.fromhex(entry["source_hex"])))
                    if actual != bytes.fromhex(entry["source_hex"]):
                        raise ValueError(f"source text mismatch: {language}:{entry['id']}")
                entry.pop("translation", None)
                entry.pop("translation_byte_length", None)
            target = output_dir / f"{block}_jpn.json"
            target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8", newline="\r\n")
            print(target, len(document["entries"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=DEFAULT_WORKSPACE)
    args = parser.parse_args()
    extract(args.workspace.resolve())


if __name__ == "__main__":
    main()
