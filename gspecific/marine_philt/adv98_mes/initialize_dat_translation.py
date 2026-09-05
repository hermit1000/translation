#!/usr/bin/env python3
"""Create a line-oriented translation document for Marine Philt TCM DAT text."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def build(source: Path) -> tuple[dict, dict]:
    data = source.read_bytes()
    records = []
    paragraphs = []
    pos = 0
    paragraph_lines = []
    paragraph_no = 0
    for raw in data.splitlines(keepends=True):
        body = raw.rstrip(b"\r\n")
        # 0x1A is the DOS text EOF marker, not a translatable line.
        if body.strip() and body != b"\x1a":
            text = body.decode("cp932")
            records.append({"id": f"text:{pos:05X}", "offset": f"{pos:05X}",
                            "paragraph": f"paragraph:{paragraph_no:03d}",
                            "end": f"{pos + len(body) - 1:05X}", "raw_hex": body.hex(" ").upper(),
                            "original": text, "display_cells": len(text), "translation": "",
                            "status": "incomplete: untranslated text"})
            paragraph_lines.append(records[-1])
        elif paragraph_lines:
            paragraphs.append({"id": f"paragraph:{paragraph_no:03d}",
                               "line_offsets": [r["offset"] for r in paragraph_lines],
                               "original": "".join(r["original"].lstrip() for r in paragraph_lines),
                               "translation": ""})
            paragraph_no += 1
            paragraph_lines = []
        pos += len(raw)
    if paragraph_lines:
        paragraphs.append({"id": f"paragraph:{paragraph_no:03d}",
                           "line_offsets": [r["offset"] for r in paragraph_lines],
                           "original": "".join(r["original"].lstrip() for r in paragraph_lines),
                           "translation": ""})
    info = {"format": "marine-philt-text-info-v1", "language": "jpn",
            "source": f"TCM/{source.name}", "source_size": len(data),
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "encoding": "cp932", "line_ending": "CRLF", "records": records,
            "paragraphs": paragraphs}
    lang = {"format": "marine-philt-text-lang-v1", "source_info": f"{source.name}_info.json",
            "records": [{k: r[k] for k in ("id", "offset", "original", "translation", "status")} for r in records],
            "paragraphs": paragraphs}
    return info, lang

def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2).replace("\n", "\r\n") + "\r\n", encoding="utf-8", newline="")

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("workspace", type=Path, nargs="?", default=Path(r"C:\work_han\workspace4"))
    ap.add_argument("--file", default="OPEN.DAT")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(); ws = a.workspace.resolve(); src = ws / "jpn-pc98" / "TCM" / a.file
    out = ws / "script-pc98" / "TCM"; info_path = out / f"{src.name}_info.json"; lang_path = out / f"{src.name}_lang.json"
    if not src.is_file(): raise FileNotFoundError(src)
    info, lang = build(src)
    if not a.force and (info_path.exists() or lang_path.exists()): raise FileExistsError("output exists; use --force")
    if a.force and lang_path.exists():
        old = json.loads(lang_path.read_text(encoding="utf-8")); prev = {r.get("offset"): r for r in old.get("records", [])}
        for r in lang["records"]:
            if r["offset"] in prev and prev[r["offset"]].get("original") == r["original"]:
                r["translation"], r["status"] = prev[r["offset"]].get("translation", ""), prev[r["offset"]].get("status", r["status"])
    write(info_path, info); write(lang_path, lang)
    print(json.dumps({"info": str(info_path), "lang": str(lang_path), "records": len(lang["records"])}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
