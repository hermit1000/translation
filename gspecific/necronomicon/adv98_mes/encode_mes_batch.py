#!/usr/bin/env python3
"""Encode all translated Necronomicon MES files in a workspace."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


# Debug-only index range: 1-based and inclusive within the selected MES list.
# Examples: (4, 4) encodes only the 4th item; (4, 8) encodes items 4 through 8.
# Leave both as None to encode the complete list.
DEBUG_INDEX_RANGE = (None, None)
# DEBUG_INDEX_RANGE = (4, 4)
# DEBUG_INDEX_RANGE = (4, 8)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=Path(r"C:\work_han\workspace1"))
    parser.add_argument("--files", nargs="+", metavar="MES")
    parser.add_argument(
        "--font-table",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "font_table-kor-jin-necro-compact.json",
    )
    parser.add_argument(
        "--compact-remap",
        "--marine-remap",
        dest="compact_remap",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "necro_compact_font_mapping_top20.json",
        help="map selected frequent characters to ADV98 one-byte compressed glyph codes",
    )
    parser.add_argument(
        "--no-compact-remap",
        dest="compact_remap",
        action="store_const",
        const=None,
        help="disable the default Necronomicon compact character remap",
    )
    parser.add_argument("--no-dosbox-x", action="store_true")
    parser.add_argument("--manifest-dir", type=Path)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_dir = workspace / "jpn-pc98" / "MES"
    script_dir = workspace / "script-pc98" / "MES"
    output_dir = workspace / "kor-pc98" / "MES"
    dosbox_dir = workspace / "kor-pc98-dosbox-x" / "MES"
    names = args.files or [
        path.name for path in sorted(source_dir.iterdir()) if path.is_file() and path.suffix.upper() == ".MES"
    ]
    if not names:
        raise SystemExit(f"no MES files found: {source_dir}")

    debug_start, debug_end = DEBUG_INDEX_RANGE
    # debug_start, debug_end = (13, 14)
    # debug_start, debug_end = (4, 4)
    # debug_start, debug_end = (204, 205)
    if debug_start is not None or debug_end is not None:
        start = 1 if debug_start is None else debug_start
        end = len(names) if debug_end is None else debug_end
        if start < 1 or start > end or end > len(names):
            raise ValueError(
                f"invalid DEBUG_INDEX_RANGE={DEBUG_INDEX_RANGE}; expected 1 <= start <= end <= {len(names)}"
            )
    else:
        start = 1
        end = len(names)

    failures = encoded = 0
    module = "gspecific.necronomicon.adv98_mes.encode_mes"
    repo_root = Path(__file__).resolve().parents[3]
    for index, name in enumerate(names, 1):
        if not start <= index <= end:
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
            module,
            str(source),
            str(info),
            str(lang),
            str(output),
            str(args.font_table.resolve()),
        ]
        if args.compact_remap:
            command += ["--compact-remap", str(args.compact_remap.resolve())]
        if args.manifest_dir:
            command += ["--patch-manifest", str((args.manifest_dir / f"{name}.patches.json").resolve())]
        print(f"[{index}/{len(names)}] {name}")
        result = subprocess.run(command, cwd=repo_root)
        if result.returncode:
            failures += 1
            print(f"{name}: failed (exit {result.returncode})", file=sys.stderr)
            continue
        if not args.no_dosbox_x:
            dosbox_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(output, dosbox_dir / name)
        encoded += 1
    print(f"encoded: {encoded}; failed: {failures}; total: {len(names)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
