#!/usr/bin/env python3
"""Encode one Marine Philt line-oriented DAT translation document."""
from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path
from mes.adv_common.text import load_font_codes, encode_translation
from mes.adv_common.patches import apply_replacements

def wrap_paragraph(text: str, records: list[dict]) -> list[str]:
    """Wrap one paragraph into the original line count and available widths."""
    text = "".join(text.splitlines()).strip()
    widths = [len(r["original"]) for r in records]
    indents = [len(r["original"]) - len(r["original"].lstrip()) for r in records]
    capacities = [w - i for w, i in zip(widths, indents)]
    if len(text) > sum(capacities):
        raise ValueError(f"paragraph translation is too long: {len(text)} > {sum(capacities)} characters")
    lines = []
    # These marks should remain attached to the preceding character rather
    # than appearing as the first glyph of a new line.
    leading_punctuation = set(".,!?;:)]}」』】〉》…·")
    cursor = 0
    for index, capacity in enumerate(capacities):
        take = min(capacity, len(text) - cursor)
        # Prefer a natural break at a space, but never exceed the line width.
        end = cursor + take
        remaining_capacity = sum(capacities[index + 1 :])
        if end < len(text) and remaining_capacity >= len(text) - end:
            split = text.rfind(" ", cursor, end + 1)
            if split > cursor + max(3, capacity // 2) and remaining_capacity >= len(text) - split:
                end = split
        if end < len(text) and text[end] in leading_punctuation and end > cursor:
            # Leave one cell of the current line unused and carry its last
            # ordinary glyph to the next line, keeping punctuation attached.
            end -= 1
        # Keep short Korean sentence endings such as ``니다.`` together.
        # If a boundary would split the final two characters from their
        # punctuation, move the whole suffix to the next line.
        for look_ahead in range(1, 4):
            punct = end + look_ahead
            if punct < len(text) and text[punct] in leading_punctuation:
                protected_start = punct - 2
                if cursor < protected_start < end:
                    end = protected_start
                break
        lines.append(text[cursor:end].rstrip() + " " * max(0, capacity - (end - cursor)))
        cursor = end
        while cursor < len(text) and text[cursor] == " ": cursor += 1
    if cursor < len(text): raise ValueError("paragraph wrapping failed")
    return [r["original"][:ind] + line for r, ind, line in zip(records, indents, lines)]

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source_dat", type=Path); ap.add_argument("info_json", type=Path); ap.add_argument("lang_json", type=Path); ap.add_argument("output_dat", type=Path)
    ap.add_argument("--no-dosbox-x", action="store_true")
    ap.add_argument("font_table", type=Path, nargs="?", default=Path("font_table/font_table-kor-jin.json")); a = ap.parse_args()
    source = a.source_dat.read_bytes(); info = json.loads(a.info_json.read_text(encoding="utf-8")); lang = json.loads(a.lang_json.read_text(encoding="utf-8"))
    if hashlib.sha256(source).hexdigest() != info["source_sha256"]: raise ValueError("source DAT SHA-256 does not match info JSON")
    if lang.get("source_info") != a.info_json.name: raise ValueError("lang JSON refers to a different info JSON")
    by_offset = {r["offset"]: r for r in info["records"]}; replacements=[]; codes=None
    entries = {r.get("offset"): r for r in lang.get("records", [])}
    # Paragraph translations take precedence and are redistributed across lines.
    for paragraph in lang.get("paragraphs", []):
        translation = paragraph.get("translation", "")
        if not translation: continue
        records = [by_offset[o] for o in paragraph.get("line_offsets", [])]
        wrapped = wrap_paragraph(translation, records)
        for record, value in zip(records, wrapped):
            entry = entries.get(record["offset"])
            if entry is None: raise ValueError(f"missing line entry at {record['offset']}")
            entry["translation"] = value; entry["status"] = "paragraph-applied"
    for entry in lang.get("records", []):
        record=by_offset.get(entry.get("offset"));
        if not record or record.get("original") != entry.get("original"): raise ValueError(f"record mismatch at {entry.get('offset')}")
        text=entry.get("translation", "")
        if not text: entry["status"]="incomplete: untranslated text"; continue
        if text == "@keep": entry["status"]="passed"; continue
        expected_cells = int(record.get("display_cells", len(record["original"])))
        if not any(p.get("translation") and entry.get("offset") in p.get("line_offsets", []) for p in lang.get("paragraphs", [])) and len(text) != expected_cells:
            raise ValueError(
                f"display length mismatch at {entry.get('offset')}: "
                f"expected exactly {expected_cells} characters, got {len(text)}"
            )
        if codes is None: codes=load_font_codes(a.font_table)
        start,end=int(record["offset"],16),int(record["end"],16); expected=bytes.fromhex(record["raw_hex"])
        if source[start:end+1] != expected: raise ValueError(f"source bytes mismatch at {start:05X}-{end:05X}")
        # OPEN.DAT uses U+3000 for visual indentation.  The project font
        # table represents that full-width blank as ``_`` (code 8140).
        encoded_text = text.replace("　", "_")
        replacements.append((start,end,encode_translation(encoded_text,codes,forbidden_control_pairs=frozenset()))); entry["status"]="passed"
    source = apply_replacements(source, replacements)
    a.output_dat.parent.mkdir(parents=True,exist_ok=True); a.output_dat.write_bytes(source)
    if not a.no_dosbox_x and a.output_dat.parent.parent.name.lower() == "kor-pc98":
        workspace = a.output_dat.parent.parent.parent
        destination = workspace / "kor-pc98-dosbox-x" / a.output_dat.parent.name / a.output_dat.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(a.output_dat, destination)
    a.lang_json.write_text(json.dumps(lang,ensure_ascii=False,indent=2).replace("\n","\r\n")+"\r\n",encoding="utf-8",newline="")
    print(json.dumps({"output":str(a.output_dat.resolve()),"replacements":len(replacements),"output_size":len(source)})); return 0
if __name__ == "__main__": raise SystemExit(main())
