"""Encode all translated Marine Philt MES files in a workspace."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=Path(r"C:\work_han\workspace4"))
    parser.add_argument("--files", nargs="+", metavar="MES")
    parser.add_argument("--font-table", type=Path, default=Path("font_table/font_table-kor-jin.json"))
    parser.add_argument(
        "--marine-remap",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "marine_compact_font_mapping_top20.json",
        help="Marine compressed glyph remap table (enabled by default)",
    )
    parser.add_argument("--no-dosbox-x", action="store_true")
    parser.add_argument("--allow-oversize-segments", action="store_true",
                        help="warn instead of stopping for {next} segments over 81 cells")
    parser.add_argument("--manifest-dir", type=Path, help="write per-MES patch manifests")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    source_dir = workspace / "jpn-pc98" / "MES"
    script_dir = workspace / "script-pc98" / "MES"
    output_dir = workspace / "kor-pc98" / "MES"
    names = args.files or [path.name for path in sorted(source_dir.glob("*.MES"))]
    failures = encoded = 0
    for index, name in enumerate(names, 1):
        source = source_dir / name
        info = script_dir / f"{name}_info.json"
        lang = script_dir / f"{name}_lang.json"
        missing = [str(path) for path in (source, info, lang) if not path.is_file()]
        if missing:
            print(f"{name}: missing {', '.join(missing)}", file=sys.stderr)
            print("stopped: batch encoding aborted", file=sys.stderr)
            return 1
        output = output_dir / name
        command = [
            sys.executable, "-m", "gspecific.marine_philt.adv98_mes.encode_mes",
            str(source), str(info), str(lang), str(output), str(args.font_table.resolve()),
            "--marine-remap", str(args.marine_remap.resolve()),
        ]
        if args.allow_oversize_segments:
            command.append("--allow-oversize-segments")
        if args.manifest_dir:
            command += ["--patch-manifest", str((args.manifest_dir / f"{name}.patches.json").resolve())]
        print(f"[{index}/{len(names)}] {name}")
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[3])
        if result.returncode:
            print(f"stopped: batch encoding aborted at {name}", file=sys.stderr)
            return 1
        if not args.no_dosbox_x:
            destination = workspace / "kor-pc98-dosbox-x" / "MES" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(output, destination)
        encoded += 1
    print(f"encoded: {encoded}; failed: {failures}; total: {len(names)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
