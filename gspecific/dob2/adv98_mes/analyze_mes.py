"""Compare conservative structured ASCII extraction with existing DOB2 records.

Only writes a review report. Existing info/lang and game files are not updated.
CONTROL_08 observations describe byte layout, not a proven command signature.
"""

import argparse
import json
from pathlib import Path

from .decode_mes import decode_mes, make_records
from mes.adv_common.tokens import verify_tokens


def analyze(data: bytes) -> dict:
    legacy = decode_mes(data)
    structured = decode_mes(data, structured_ascii=True)
    verify_tokens(data, structured)
    old = make_records(legacy)
    new = make_records(structured)
    old_text = {r["offset"]: r for r in old if r["type"] == "text"}
    new_text = {r["offset"]: r for r in new if r["type"] == "text"}
    changes = []
    for offset in sorted(old_text.keys() | new_text.keys()):
        before, after = old_text.get(offset), new_text.get(offset)
        if before != after:
            changes.append({"offset": offset, "before": before, "after": after})
    speakers = []
    for token in legacy:
        if token["type"] != "control" or token["value"] != "CONTROL_08":
            continue
        start = token["offset"]
        bracket = None
        if data[start + 1:start + 3] == b"\x81\x6d":
            bracket = start + 1
        elif data[start + 2:start + 4] == b"\x81\x6d":
            bracket = start + 2
        if bracket is None:
            continue
        # Require a closing speaker bracket in contiguous DBCS label bytes.
        cursor = bracket + 2
        while cursor + 1 < len(data):
            pair = data[cursor:cursor + 2]
            if pair == b"\x81\x6e":
                break
            try:
                if len(pair.decode("cp932")) != 1:
                    break
            except UnicodeDecodeError:
                break
            cursor += 2
        if data[cursor:cursor + 2] != b"\x81\x6e":
            continue
        speakers.append({
            "control_offset": f"{start:05X}", "label_offset": f"{bracket:05X}",
            "label_end": f"{cursor + 1:05X}",
            "label": data[bracket:cursor + 2].decode("cp932"),
            "prefix_hex": data[start + 1:bracket].hex(" ").upper(),
            "legacy_splits_opening_bracket": bracket < start + token["size"],
            "interpretation": "observed-layout-only",
        })
    return {"source_size": len(data), "lossless": True,
            "ascii_outputs": [{"offset": f'{t["offset"]:05X}', "size": t["size"],
                               "text": t["value"]} for t in structured
                              if t.get("syntax") == "ascii-output-nul"],
            "text_record_changes": changes, "speaker_layouts": speakers}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    paths = [args.input] if args.input.is_file() else sorted(args.input.rglob("*.MES"))
    if not paths:
        parser.error("no MES files found")
    files = {str(p.relative_to(args.input) if args.input.is_dir() else p.name): analyze(p.read_bytes())
             for p in paths}
    summary = {"files": len(files),
               **{key: sum(len(f[key]) for f in files.values()) for key in
                  ("ascii_outputs", "text_record_changes", "speaker_layouts")}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "files": files}, ensure_ascii=False,
                                     indent=2) + "\n", encoding="utf-8", newline="\r\n")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
