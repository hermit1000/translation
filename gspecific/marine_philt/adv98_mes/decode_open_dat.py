#!/usr/bin/env python3
"""Decode Marine Philt's plain-text TCM/OPEN.DAT into info/lang JSON."""
from __future__ import annotations
import argparse
from pathlib import Path
from .initialize_dat_translation import build, write

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("workspace", type=Path, nargs="?", default=Path(r"C:\work_han\workspace4"))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(); ws = a.workspace.resolve(); src = ws / "jpn-pc98" / "TCM" / "OPEN.DAT"
    out = ws / "script-pc98" / "TCM"; ip = out / "OPEN.DAT_info.json"; lp = out / "OPEN.DAT_lang.json"
    if not a.force and (ip.exists() or lp.exists()): raise FileExistsError("output exists; use --force")
    info, lang = build(src)
    if a.force and lp.exists():
        import json
        old = json.loads(lp.read_text(encoding="utf-8")); prev = {r.get("offset"): r for r in old.get("records", [])}
        for r in lang["records"]:
            if r["offset"] in prev and prev[r["offset"]].get("original") == r["original"]:
                r["translation"] = prev[r["offset"]].get("translation", "")
    write(ip, info); write(lp, lang); print(f"decoded OPEN.DAT: {len(lang['records'])} text lines"); return 0
if __name__ == "__main__": raise SystemExit(main())
