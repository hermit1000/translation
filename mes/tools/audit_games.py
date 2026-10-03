"""Read-only DOB1/Marine review: macro boundaries, ASCII and speaker compatibility.

The requested JSON report is the only output. Source and translation files are
never rewritten. This is lexical evidence, not a complete control-flow parser.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .ascii import resolve_ascii_and_gaiji
from .text import load_font_codes
from .tokens import verify_tokens
from gspecific.dob1.adv98_mes import decode_mes as dob1
from gspecific.dob2.adv98_mes.encode_mes import encode_record_translation
from gspecific.marine_philt.adv98_mes import decode_mes as marine


def compare_macros(data: bytes, tokens: list[dict]) -> dict:
    """Compare historical raw BA search with current lexical call boundaries."""
    lexical = {}
    for token, operand in zip(tokens, tokens[1:]):
        if token["type"] == "command" and token["value"] == "CALL_BUILTIN" and operand["type"] == "argument":
            lexical[token["offset"]] = (operand["offset"] + operand["size"] - 1, operand["value"])
    raw = {}
    for start in range(len(data) - 1):
        if data[start] != 0xBA:
            continue
        value = data[start + 1]
        if value == 0x28 and start + 2 < len(data):
            raw[start] = (start + 2, data[start + 2])
        elif 0x23 <= value <= 0x27:
            raw[start] = (start + 1, value - 0x23)
    differences = []
    for start in sorted(raw.keys() | lexical.keys()):
        if raw.get(start) == lexical.get(start):
            continue
        owner = next(t for t in tokens if t["offset"] <= start < t["offset"] + t["size"])
        differences.append({"offset": f"{start:05X}", "raw": raw.get(start),
                            "lexical": lexical.get(start), "containing_token": owner})
    return {"raw_calls": len(raw), "lexical_calls": len(lexical), "differences": differences}


def compare_ascii(data: bytes, before: list[dict], after: list[dict]) -> dict:
    verify_tokens(data, before)
    verify_tokens(data, after)
    old = {r["offset"]: r for r in dob1.make_readable_records(before) if r["type"] == "text"}
    new = {r["offset"]: r for r in dob1.make_readable_records(after) if r["type"] == "text"}
    return {"outputs": sum(t.get("syntax") == "ascii-output-nul" for t in after),
            "text_changes": [{"offset": offset, "before": old.get(offset), "after": new.get(offset)}
                             for offset in sorted(old.keys() | new.keys()) if old.get(offset) != new.get(offset)]}


def audit_dob1(workspace: Path) -> dict:
    files = {}
    for path in sorted((workspace / "jpn-pc98/MES").glob("*.MES")):
        data = path.read_bytes()
        tokens = dob1.decode_mes(data)
        files[path.name] = {"macros": compare_macros(data, tokens),
                            "ascii": compare_ascii(data, tokens, dob1.decode_mes(data, ascii_output=True))}
    if not files:
        raise ValueError(f"no DOB1 MES files: {workspace}")
    return files


def encode_result(original: str, translation: str, codes: dict, raw: bytes, repairs: bool) -> dict:
    try:
        output = encode_record_translation(original, translation, codes, raw, width=28, speaker_repairs=repairs)
        return {"status": "ok", "size": len(output), "sha256": hashlib.sha256(output).hexdigest()}
    except (ValueError, UnicodeError) as exc:
        return {"status": "error", "error": str(exc)}


def audit_marine(workspace: Path, codes: dict) -> dict:
    files = {}
    for path in sorted((workspace / "jpn-pc98/MES").glob("*.MES")):
        data = path.read_bytes()
        tokens = marine.decode_mes(data, structured_ascii=False)
        structured = resolve_ascii_and_gaiji(data, marine._consume_marine_parameters(
            dob1.decode_mes(data, parameter_controls=(0x08, 0x09, 0x0C, 0x0D, 0x19), ascii_output=True), data))
        result = {"ascii": compare_ascii(data, tokens, structured),
                  "selectors": [{"offset": f'{t["offset"]:05X}', "bytes": t["bytes"]}
                                for t in tokens if t.get("parameters") is not None],
                  "counts": {}, "differences": [], "errors": [], "range_repairs": []}
        files[path.name] = result
        info_path = workspace / "script-pc98/MES" / f"{path.name}_info.json"
        lang_path = workspace / "script-pc98/MES" / f"{path.name}_lang.json"
        if not info_path.exists() or not lang_path.exists():
            result["translation_metadata"] = "missing"
            continue
        info = json.loads(info_path.read_text(encoding="utf-8"))
        lang = json.loads(lang_path.read_text(encoding="utf-8"))
        if hashlib.sha256(data).hexdigest() != info["source_sha256"] or lang.get("source_info") != info_path.name:
            raise ValueError(f"source metadata mismatch: {path.name}")
        records = {r.get("offset"): r for r in info["records"]}
        counts = Counter()
        for entry in lang.get("dialogue_groups", []) + lang.get("overlay_texts", []):
            translation = entry.get("translation")
            if not translation or translation == "@keep":
                continue
            record = records.get(entry.get("offset"))
            if not record or record["type"] != "text" or entry.get("original") != record["original"]:
                raise ValueError(f"text metadata mismatch: {path.name} {entry.get('offset')}")
            start, end = int(record["offset"], 16), int(record["end"], 16)
            raw = bytes.fromhex(record["raw_hex"])
            if data[start:end + 1] != raw:
                raise ValueError(f"source range mismatch: {path.name} {start:05X}")
            original = record["original"]
            if (start > 0 and data[start - 1:start + 1] == b"\x81\x6d" and original.startswith("め")
                    and "［" not in original and "］" in original):
                result["range_repairs"].append(record["offset"])
            before = encode_result(original, translation, codes, raw, True)
            after = encode_result(original, translation, codes, raw, False)
            counts["translated"] += 1
            counts[after["status"]] += 1
            if before != after:
                result["differences"].append({"offset": record["offset"], "before": before, "after": after})
            if after["status"] == "error":
                result["errors"].append({"offset": record["offset"], **after})
        result["counts"] = dict(counts)
    if not files:
        raise ValueError(f"no Marine MES files: {workspace}")
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dob1_workspace", type=Path)
    parser.add_argument("marine_workspace", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--font-table", type=Path, default=Path("font_table/font_table-kor-jin.json"))
    args = parser.parse_args()
    first = audit_dob1(args.dob1_workspace)
    second = audit_marine(args.marine_workspace, load_font_codes(args.font_table))
    counts = Counter()
    for f in second.values():
        counts.update(f["counts"])
    summary = {"dob1_files": len(first), "marine_files": len(second),
               "macro_calls": sum(f["macros"]["lexical_calls"] for f in first.values()),
               "macro_differences": sum(len(f["macros"]["differences"]) for f in first.values()),
               "marine_encoding": dict(counts),
               "marine_encoding_differences": sum(len(f["differences"]) for f in second.values()),
               "marine_range_repairs": sum(len(f["range_repairs"]) for f in second.values()),
               "marine_selectors": sum(len(f["selectors"]) for f in second.values()),
               "ascii": {name: {"outputs": sum(f["ascii"]["outputs"] for f in files.values()),
                                "text_changes": sum(len(f["ascii"]["text_changes"]) for f in files.values())}
                         for name, files in (("dob1", first), ("marine", second))}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "dob1": first, "marine": second},
                                     ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\r\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
