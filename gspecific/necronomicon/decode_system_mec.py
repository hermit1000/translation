#!/usr/bin/env python3
"""Decode Necronomicon's embedded SYSTEM.MEC menu strings."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .system_mec import (
        DEFAULT_TEXT_SPEC,
        FORMAT,
        decode_adv98_bytes,
        make_info,
        write_document,
    )
except ImportError:  # Support direct execution: python decode_system_mec.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from system_mec import (  # type: ignore
        DEFAULT_TEXT_SPEC,
        FORMAT,
        decode_adv98_bytes,
        make_info,
        write_document,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_mec", type=Path)
    parser.add_argument("output_info", type=Path)
    parser.add_argument("output_lang", type=Path)
    parser.add_argument("--text-spec", type=Path, default=None)
    args = parser.parse_args()

    info = make_info(args.source_mec, args.text_spec or DEFAULT_TEXT_SPEC)
    entries = []
    source = args.source_mec.read_bytes()
    for record in info["records"]:
        raw = bytes.fromhex(record["raw_hex"])
        if record.get("variable_tokens"):
            original = record["original"]
        else:
            original = decode_adv98_bytes(raw)
            if original != record["original"]:
                raise ValueError(
                    f"decoded text mismatch at {record['offset']}: {original!r}"
                )
        entries.append(
            {
                "id": f"system-mec:{record['offset']}",
                "offset": record["offset"],
                "original": original,
                "translation": "",
                "status": "untranslated",
            }
        )

    write_document(args.output_info, info)
    write_document(
        args.output_lang,
        {
            "format": FORMAT,
            "source_info": args.output_info.name,
            "source_sha256": info["source_sha256"],
            "entries": entries,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
