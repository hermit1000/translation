#!/usr/bin/env python3
"""Build every translated ADV98 MES under a workspace directory."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=Path(r"C:\work_han\workspace2"), help="workspace2 (or another compatible workspace) directory")
    parser.add_argument("--font-table", type=Path, default=Path("font_table/font_table-kor-jin.json"))
    parser.add_argument("--dosbox-x", dest="dosbox_x", action="store_true", default=True, help="also copy outputs to kor-pc98-dosbox-x/MES (default)")
    parser.add_argument("--no-dosbox-x", dest="dosbox_x", action="store_false", help="do not copy outputs to kor-pc98-dosbox-x/MES")
    args = parser.parse_args()

    root = args.workspace.resolve()
    script_dir = root / "script-pc98" / "MES"
    jpn_dir = root / "jpn-pc98" / "MES"
    kor_dir = root / "kor-pc98" / "MES"
    if not script_dir.is_dir():
        raise SystemExit(f"translation directory not found: {script_dir}")
    font_table = args.font_table.resolve()
    manifests = sorted(script_dir.glob("*_kor.json"))
    lang_manifests = sorted(script_dir.glob("*_lang.json"))
    if lang_manifests:
        command = [sys.executable, "-m", "gspecific.dob1.adv98_mes.encode_mes_batch", str(root)]
        if not args.dosbox_x:
            command.append("--no-dosbox-x")
        result = subprocess.run(command, check=False)
        return result.returncode
    if not manifests:
        raise SystemExit(f"no *_kor.json files found in {script_dir}")

    built = []
    for manifest in manifests:
        document = json.loads(manifest.read_text(encoding="utf-8"))
        source_name = Path(document.get("source", "")).name
        if not source_name:
            source_name = manifest.name.removesuffix("_kor.json")
        source = jpn_dir / source_name
        output = kor_dir / source_name
        command = [
            sys.executable,
            "-m",
            "gspecific.dob1.adv98_mes.encode_mes",
            str(source),
            str(manifest),
            str(output),
            str(font_table),
        ]
        subprocess.run(command, check=True)
        if args.dosbox_x:
            dosbox_output = root / "kor-pc98-dosbox-x" / "MES" / source_name
            dosbox_output.parent.mkdir(parents=True, exist_ok=True)
            dosbox_output.write_bytes(output.read_bytes())
        built.append(str(output))

    print(json.dumps({"workspace": str(root), "built_count": len(built), "outputs": built}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
