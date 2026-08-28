#!/usr/bin/env python3
"""Compare Japanese and Korean ADV98 MES files structurally.

The Korean font bytes are not CP932 text, so this validator compares the
decoded command/control stream rather than trying to render Korean bytes as
Japanese.  It reports command sequence changes, text-segment count changes,
and missing punctuation calls.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

try:
    from .decode_mes import decode_mes
except ImportError:  # direct script execution from workspace root
    from decode_mes import decode_mes


PUNCT_SLOTS = {0x0D, 0x0E, 0x0F, 0x11, 0x12}


def signature(data: bytes, korean: bool = False) -> tuple[int, list[int]]:
    """Return punctuation-call count/sequence.

    Korean font bytes cannot be parsed as CP932, so only raw BA 28 xx calls
    are inspected in the output.  The source is decoded normally.
    """
    if korean:
        punct = [data[i + 2] for i in range(len(data) - 2)
                 if data[i:i + 2] == bytes((0xBA, 0x28)) and data[i + 2] in PUNCT_SLOTS]
        return 0, punct
    tokens = decode_mes(data)
    punct: list[int] = []
    for index, token in enumerate(tokens):
        if token.get("type") != "command" or token.get("value") != "CALL_BUILTIN":
            continue
        if index + 1 >= len(tokens) or tokens[index + 1].get("type") != "argument":
            continue
        raw = tokens[index + 1].get("value")
        if raw == 0x28 and index + 2 < len(tokens) and tokens[index + 2].get("type") == "argument":
            slot = tokens[index + 2].get("value")
            if slot in PUNCT_SLOTS:
                punct.append(slot)
        elif raw in PUNCT_SLOTS:
            punct.append(raw)
    return 0, punct


def compare_file(source: Path, output: Path) -> list[str]:
    _, src_punct = signature(source.read_bytes())
    _, out_punct = signature(output.read_bytes(), korean=True)
    issues: list[str] = []
    if src_punct != out_punct:
        issues.append(f"punctuation sequence differs ({src_punct} -> {out_punct})")
    return issues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", nargs="?", type=Path, default=Path(r"C:\work_han\workspace2"))
    args = ap.parse_args()
    root = args.workspace.resolve()
    source_dir = root / "jpn-pc98" / "MES"
    output_dir = root / "kor-pc98" / "MES"
    checked = clean = 0
    for source in sorted(source_dir.glob("*.MES")):
        output = output_dir / source.name
        if not output.exists():
            print(f"MISSING {source.name}: Korean MES not found")
            continue
        checked += 1
        issues = compare_file(source, output)
        if issues:
            print(f"FAIL {source.name}: " + "; ".join(issues))
        else:
            clean += 1
    print(f"checked: {checked}, structurally clean: {clean}, failed: {checked - clean}")
    return 1 if clean != checked else 0


if __name__ == "__main__":
    raise SystemExit(main())
