#!/usr/bin/env python3
"""Encode all Marine Philt DAT translation documents in a workspace."""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path
def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("workspace",type=Path,nargs="?",default=Path(r"C:\work_han\workspace4")); ap.add_argument("--files",nargs="+"); ap.add_argument("--font-table",type=Path,default=Path("font_table/font_table-kor-jin.json")); a=ap.parse_args(); ws=a.workspace.resolve(); src=ws/"jpn-pc98"/"TCM"; script=ws/"script-pc98"/"TCM"; out=ws/"kor-pc98"/"TCM"; names=a.files or [p.name.removesuffix("_lang.json") for p in sorted(script.glob("*_lang.json"))]; fail=0
    for name in names:
        cmd=[sys.executable,"-m","gspecific.marine_philt.adv98_mes.encode_dat",str(src/name),str(script/f"{name}_info.json"),str(script/f"{name}_lang.json"),str(out/name),str(a.font_table.resolve())]; print(name); fail += subprocess.run(cmd,cwd=Path(__file__).resolve().parents[3]).returncode != 0
    print(f"encoded: {len(names)-fail}; failed: {fail}; total: {len(names)}"); return 1 if fail else 0
if __name__ == "__main__": raise SystemExit(main())
