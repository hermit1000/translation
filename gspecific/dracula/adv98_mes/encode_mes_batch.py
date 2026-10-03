#!/usr/bin/env python3
"""Encode all translated Dracula MES files in a workspace."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


# Debug-only index range: 1-based and inclusive within the selected MES list.
# Leave both as None to encode the complete list.
DEBUG_INDEX_RANGE = (None, None)
# DEBUG_INDEX_RANGE = (4, 4)
# DEBUG_INDEX_RANGE = (4, 8)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workspace",
        type=Path,
        nargs="?",
        default=Path(r"C:\work_han\workspace2"),
        help="workspace containing jpn-pc98, script-pc98, kor-pc98, and kor-pc98-dosbox-x",
    )
    parser.add_argument("--files", nargs="+", metavar="MES")
    parser.add_argument(
        "--font-table",
        type=Path,
        default=Path("font_table/font_table-kor-jin.json"),
        help="font table passed to encode_mes.py",
    )
    parser.add_argument("--no-dosbox-x", action="store_true")
    parser.add_argument("--manifest-dir", type=Path, help="write per-MES patch manifests")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = args.workspace.resolve()
    source_dir = workspace / "jpn-pc98" / "MES"
    script_dir = workspace / "script-pc98" / "MES"
    output_dir = workspace / "kor-pc98" / "MES"
    dosbox_output_dir = workspace / "kor-pc98-dosbox-x" / "MES"
    names = args.files or [
        path.name for path in sorted(source_dir.iterdir()) if path.is_file() and path.suffix.upper() == ".MES"
    ]
    if not names:
        raise SystemExit(f"no MES files found: {source_dir}")

    debug_start, debug_end = DEBUG_INDEX_RANGE
    # debug_start, debug_end = (108, 113)
    if debug_start is not None or debug_end is not None:
        debug_start = 1 if debug_start is None else debug_start
        debug_end = len(names) if debug_end is None else debug_end
        if not 1 <= debug_start <= debug_end <= len(names):
            raise SystemExit(
                f"invalid DEBUG_INDEX_RANGE={DEBUG_INDEX_RANGE}; expected 1 <= START <= END <= {len(names)}"
            )
    else:
        debug_start, debug_end = 1, len(names)

    font_table = args.font_table.resolve()
    failures = encoded = 0
    for index, name in enumerate(names, 1):
        if not debug_start <= index <= debug_end:
            continue
        source = source_dir / name
        info = script_dir / f"{name}_info.json"
        lang = script_dir / f"{name}_lang.json"
        output = output_dir / name
        missing = [str(path) for path in (source, info, lang) if not path.is_file()]
        if missing:
            print(f"{name}: missing {', '.join(missing)}", file=sys.stderr)
            failures += 1
            continue
        command = [
            sys.executable,
            "-m",
            "gspecific.dracula.adv98_mes.encode_mes",
            str(source),
            str(info),
            str(lang),
            str(output),
            str(font_table),
        ]
        if args.manifest_dir:
            command += ["--patch-manifest", str((args.manifest_dir / f"{name}.patches.json").resolve())]
        print(f"[{index}/{len(names)}] {name}")
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[3])
        if result.returncode:
            failures += 1
            print(f"{name}: failed (exit {result.returncode})", file=sys.stderr)
            continue
        if not args.no_dosbox_x:
            dosbox_output_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(output, dosbox_output_dir / name)
        encoded += 1

    print(f"encoded: {encoded}; failed: {failures}; total: {len(names)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
