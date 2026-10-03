#!/usr/bin/env python3
"""Compare Japanese and Korean ADV98 MES files structurally.

Without a patch manifest, compare non-text lexical tokens (not full runtime
semantics). With a manifest, verify every declared replacement and all
untouched bytes, allowing explicitly recorded macro rewrites.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

try:
    from .decode_mes import decode_mes
except ImportError:  # direct script execution from workspace root
    from decode_mes import decode_mes

from mes.adv_common.patches import verify_patch_manifest


PUNCT_SLOTS = {0x0D, 0x0E, 0x0F, 0x11, 0x12}


def signature(data: bytes, korean: bool = False) -> tuple[int, list[int]]:
    """Return punctuation-call count/sequence.

    Both streams are scanned at lexical boundaries, including quoted operands.
    The korean argument is retained for callers of the previous helper.
    """
    if korean:
        punct = [data[i + 2] for i in range(len(data) - 2)
                 if data[i:i + 2] == bytes((0xBA, 0x28)) and data[i + 2] in PUNCT_SLOTS]
        return 0, punct
    tokens = decode_mes(data, ascii_output=True)
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


def compare_file(source: Path, output: Path, manifest: Path | None = None) -> list[str]:
    original, translated = source.read_bytes(), output.read_bytes()
    if manifest is not None:
        try:
            verify_patch_manifest(original, translated, json.loads(manifest.read_text(encoding="utf-8")))
        except (ValueError, KeyError, TypeError, OSError) as exc:
            return [str(exc)]
        return []
    _, src_punct = signature(original)
    _, out_punct = signature(translated, korean=True)
    if src_punct == out_punct:
        return []
    return [f"punctuation sequence differs ({src_punct} -> {out_punct}); "
            "use a patch manifest for full byte-range validation"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", nargs="?", type=Path, default=Path(r"C:\work_han\workspace2"))
    ap.add_argument("--manifest-dir", type=Path, help="require <filename>.patches.json for every MES")
    args = ap.parse_args()
    root = args.workspace.resolve()
    source_dir = root / "jpn-pc98" / "MES"
    output_dir = root / "kor-pc98" / "MES"
    checked = clean = missing = 0
    sources = sorted(source_dir.glob("*.MES"))
    if not sources:
        print(f"FAIL no MES files found: {source_dir}")
        return 1
    for source in sources:
        output = output_dir / source.name
        if not output.exists():
            print(f"MISSING {source.name}: Korean MES not found")
            missing += 1
            continue
        checked += 1
        manifest = args.manifest_dir / f"{source.name}.patches.json" if args.manifest_dir else None
        issues = compare_file(source, output, manifest)
        if issues:
            print(f"FAIL {source.name}: " + "; ".join(issues))
        else:
            clean += 1
    print(f"checked: {checked}, validation passed: {clean}, failed: {checked - clean}, missing: {missing}")
    return 1 if clean != checked or missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
