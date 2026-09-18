"""Prepare lossless Marine ASCII metadata migration in a separate directory."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path


def preserve_translations(old_info: dict, old_lang: dict, new_info: dict, new_lang: dict) -> tuple[dict, dict]:
    if old_info["source_sha256"] != new_info["source_sha256"]:
        raise ValueError("source hash changed; cannot migrate translations")
    if old_lang["source_info"] != new_lang["source_info"]:
        raise ValueError("source info reference changed")
    old_records = {r["offset"]: r for r in old_info["records"] if r["type"] == "text"}
    new_records = {r["offset"]: r for r in new_info["records"] if r["type"] == "text"}
    result = deepcopy(old_lang)
    targets = {}
    for section in ("dialogue_groups", "overlay_texts"):
        result[section] = deepcopy(new_lang.get(section, []))
        for entry in result[section]:
            if entry["offset"] in targets:
                raise ValueError(f"duplicate new entry: {entry['offset']}")
            targets[entry["offset"]] = entry
    report = {"preserved": [], "expanded": [], "layout_kept": []}
    seen = set()
    for section in ("dialogue_groups", "overlay_texts"):
        for old in old_lang.get(section, []):
            offset = old["offset"]
            if offset in seen:
                raise ValueError(f"duplicate old entry: {offset}")
            seen.add(offset)
            previous = old_records.get(offset)
            current = new_records.get(offset)
            target = targets.get(offset)
            if not previous or previous.get("original") != old["original"]:
                raise ValueError(f"old original mismatch: {offset}")
            if not current or not target:
                raise ValueError(f"entry needs manual relocation: {offset}")
            unchanged = (previous["raw_hex"] == current["raw_hex"]
                         and previous["end"] == current["end"]
                         and previous["original"] == current["original"])
            if not unchanged:
                # Known credit form: a trailing ASCII ')' was consumed as a number.
                safe_extension = (current["original"] == previous["original"] + ")"
                                  and bytes.fromhex(current["raw_hex"]) == bytes.fromhex(previous["raw_hex"]) + b")"
                                  and int(current["end"], 16) == int(previous["end"], 16) + 1)
                if not safe_extension or old.get("translation") not in (None, "", "@keep"):
                    raise ValueError(f"changed translated range needs review: {offset}")
                report["expanded"].append(offset)
            generated = {
                key: deepcopy(target[key])
                for key in ("original", "connections", "combined_original")
                if key in target
            }
            target.update(deepcopy(old))
            target.update(generated)
            report["preserved"].append(offset)
    for offset, target in targets.items():
        if offset not in seen and target["original"].strip() == ":":
            target["translation"] = "@keep"
            target["status"] = "passed"
            report["layout_kept"].append(offset)
    return result, report


def main() -> int:
    from .decode_mes import decode_document
    from .initialize_translation import make_lang
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_mes", type=Path)
    parser.add_argument("info_json", type=Path)
    parser.add_argument("lang_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    old_info = json.loads(args.info_json.read_text(encoding="utf-8"))
    old_lang = json.loads(args.lang_json.read_text(encoding="utf-8"))
    source = args.source_mes.read_bytes()
    if hashlib.sha256(source).hexdigest() != old_info["source_sha256"]:
        raise ValueError("source MES does not match old info")
    for r in old_info["records"]:
        if r["type"] == "text" and source[int(r["offset"], 16):int(r["end"], 16) + 1] != bytes.fromhex(r["raw_hex"]):
            raise ValueError(f"old source range mismatch: {r['offset']}")
    new_info = decode_document(args.source_mes, old_info["source"])
    new_lang, report = preserve_translations(old_info, old_lang, new_info,
                                            make_lang(args.info_json.name, new_info))
    outputs = {args.info_json.name: new_info, args.lang_json.name: new_lang, "migration_report.json": report}
    for name in outputs:
        if (args.output_dir / name).exists():
            raise FileExistsError(args.output_dir / name)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs.items():
        (args.output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8", newline="\r\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
