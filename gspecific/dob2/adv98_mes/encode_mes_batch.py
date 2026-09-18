"""Encode all translated DOB2 ADV98 MES/CAL files in a workspace."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-dir", type=Path, help="write per-script patch manifests")
    parser.add_argument(
        "workspace",
        type=Path,
        nargs="?",
        default=Path(r"C:\work_han\workspace1"),
        help="workspace containing jpn-pc98, script-pc98, kor-pc98, and kor-pc98-dosbox-x",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        metavar="SCRIPT",
        help="encode only these MES/CAL filenames; by default encode every source MES/CAL",
    )
    parser.add_argument(
        "--font-table",
        type=Path,
        default=Path("font_table/font_table-kor-jin.json"),
        help="font table passed to encode_mes.py",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = args.workspace.resolve()
    source_dir = workspace / "jpn-pc98" / "MES"
    script_dir = workspace / "script-pc98" / "MES"
    output_dir = workspace / "kor-pc98" / "MES"
    dosbox_output_dir = workspace / "kor-pc98-dosbox-x" / "MES"
    names = args.files or [
        path.name
        for path in sorted(source_dir.iterdir())
        if path.is_file() and path.suffix.upper() in {".MES", ".CAL"}
    ]
    if not names:
        raise SystemExit(f"no MES/CAL files found: {source_dir}")

    font_table = args.font_table.resolve()
    failures = 0
    encoded = 0
    for name in names:
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
            "gspecific.dob2.adv98_mes.encode_mes",
            str(source),
            str(info),
            str(lang),
            str(output),
            str(font_table),
        ]
        if args.manifest_dir:
            command += ["--patch-manifest", str((args.manifest_dir / f"{name}.patches.json").resolve())]
        print(f"[{encoded + failures + 1}/{len(names)}] {name}")
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[3])
        if result.returncode:
            failures += 1
            print(f"{name}: failed (exit {result.returncode})", file=sys.stderr)
            continue
        dosbox_output_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output, dosbox_output_dir / name)
        print(f"  copied: {dosbox_output_dir / name}")
        encoded += 1

    print(f"encoded: {encoded}; failed: {failures}; total: {len(names)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
