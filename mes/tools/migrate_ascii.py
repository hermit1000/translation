"""Preview ASCII extraction changes and migrate only unchanged translations."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path


def text_records(document: dict) -> dict[str, dict]:
    result = {}
    for record in document["records"]:
        if record.get("type") != "text":
            continue
        offset = record["offset"]
        if offset in result and text_identity(result[offset]) != text_identity(record):
            raise ValueError(f"conflicting text records at {offset}")
        result[offset] = record
    return result


def text_identity(record: dict | None) -> tuple | None:
    if record is None:
        return None
    return (int(record["offset"], 16), int(record["end"], 16),
            bytes.fromhex(record["raw_hex"]), record["original"])


def prepare_migration(source: bytes, old_info: dict, old_lang: dict,
                      new_info: dict) -> tuple[dict, dict, dict]:
    digest = hashlib.sha256(source).hexdigest()
    if any(info.get("source_sha256") != digest for info in (old_info, new_info)):
        raise ValueError("source hash changed; cannot migrate translations")
    # Older DOB1 info stores only offset/end/original. Recover raw bytes from
    # the hash-verified source; never infer them by re-encoding display text.
    old_info = deepcopy(old_info)
    for record in old_info["records"]:
        if record.get("type") == "text" and "raw_hex" not in record:
            start, end = int(record["offset"], 16), int(record["end"], 16)
            if not 0 <= start <= end < len(source):
                raise ValueError(f"invalid legacy source range at {start:05X}")
            record["raw_hex"] = source[start:end + 1].hex()
    before, after = text_records(old_info), text_records(new_info)
    for records in (before, after):
        for offset, record in records.items():
            start, end, raw, _ = text_identity(record)
            if not 0 <= start <= end < len(source) or source[start:end + 1] != raw:
                raise ValueError(f"source bytes mismatch at {offset}")
    changes = [
        {"offset": offset, "before": before.get(offset), "after": after.get(offset)}
        for offset in sorted(before.keys() | after.keys(), key=lambda value: int(value, 16))
        if text_identity(before.get(offset)) != text_identity(after.get(offset))
    ]
    info, lang = deepcopy(old_info), deepcopy(old_lang)
    info.update(deepcopy(new_info))
    # Keep game annotations on records whose underlying representation survived.
    old_by_offset = {r["offset"]: r for r in old_info["records"]}
    for record in info["records"]:
        old = old_by_offset.get(record["offset"])
        if old and old.get("type") == record.get("type"):
            if record["type"] != "text" or text_identity(old) == text_identity(record):
                merged = deepcopy(old)
                merged.update(record)
                record.clear()
                record.update(merged)
    report = {"source_sha256": digest, "changes": changes,
              "preserved": [], "added": [], "review_required": []}
    dialogues = {d["id"]: d for d in old_info.get("dialogues", [])}
    new_by_offset = {r["offset"]: r for r in new_info["records"]}
    claimed: list[tuple[int, int]] = []
    seen = set()
    for section in ("dialogue_groups", "overlay_texts", "extra_texts"):
        for entry in old_lang.get(section, []):
            identifier = entry.get("id") or f"{section}:{entry.get('offset')}"
            if (section, identifier) in seen:
                report["review_required"].append({"id": identifier, "reasons": ["duplicate entry"],
                                                   "entry": deepcopy(entry)})
                continue
            seen.add((section, identifier))
            metadata = dialogues.get(entry.get("id"))
            reasons = []
            if metadata:
                offsets = [segment["offset"] for segment in metadata.get("segments", [])]
                controls = [entry["id"].split(":", 1)[1]]
                controls += [m["offset"] for m in metadata.get("macros", []) if m.get("offset")]
                for offset in controls:
                    old, new = old_by_offset.get(offset), new_by_offset.get(offset)
                    fields = ("type", "name", "macro_slot", "opcode", "arguments", "raw_hex", "value")
                    if not old or not new or any(old[k] != new.get(k) for k in fields if k in old):
                        reasons.append(f"control boundary changed at {offset}")
            else:
                offsets = [entry.get("offset")]
            for offset in offsets:
                old, new = before.get(offset), after.get(offset)
                if old:
                    claimed.append((int(old["offset"], 16), int(old["end"], 16)))
                elif entry.get("offset") and entry.get("end"):
                    claimed.append((int(entry["offset"], 16), int(entry["end"], 16)))
                if old is None or new is None or text_identity(old) != text_identity(new):
                    reasons.append(f"text range changed or missing at {offset}")
                elif not metadata and entry.get("original") != old["original"]:
                    reasons.append(f"original mismatch at {offset}")
            if reasons:
                report["review_required"].append({"id": identifier, "reasons": reasons,
                                                   "entry": deepcopy(entry)})
            else:
                report["preserved"].append(identifier)
    overlays = lang.setdefault("overlay_texts", [])
    for offset, record in after.items():
        start, end, _, original = text_identity(record)
        if any(start <= b and a <= end for a, b in claimed):
            continue
        if not record.get("translation_candidate") or not original.strip():
            continue
        overlays.append({"id": f"overlay:{offset}", "offset": offset,
                         "original": original, "translation": "",
                         "status": "incomplete: untranslated overlay"})
        report["added"].append(offset)
    report["safe_to_write"] = not report["review_required"]
    return info, lang, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", choices=("dob1", "dob2"))
    parser.add_argument("source_mes", type=Path)
    parser.add_argument("info_json", type=Path)
    parser.add_argument("lang_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    old_info = json.loads(args.info_json.read_text(encoding="utf-8"))
    old_lang = json.loads(args.lang_json.read_text(encoding="utf-8"))
    if old_lang.get("source_info") != args.info_json.name:
        raise ValueError("lang references a different info file")
    if not all(str(d.get("format", "")).startswith(args.game + "-") for d in (old_info, old_lang)):
        raise ValueError("game and document formats differ")
    if args.game == "dob1":
        from gspecific.dob1.adv98_mes.decode_mes import decode_document
    else:
        from gspecific.dob2.adv98_mes.decode_mes import decode_document
    new_info = decode_document(args.source_mes, old_info["source"], structured_ascii=True)
    new_info["format"] = old_info["format"]
    info, lang, report = prepare_migration(args.source_mes.read_bytes(), old_info, old_lang, new_info)
    outputs = {"migration_report.json": report}
    if report["safe_to_write"]:
        outputs.update({args.info_json.name: info, args.lang_json.name: lang})
    if len({args.info_json.name, args.lang_json.name, "migration_report.json"}) != 3:
        raise ValueError("output filenames collide")
    if args.output_dir.resolve() in {args.info_json.resolve().parent, args.lang_json.resolve().parent}:
        raise ValueError("migration requires a separate output directory")
    for name in outputs:
        if (args.output_dir / name).exists():
            raise FileExistsError(args.output_dir / name)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, document in outputs.items():
        (args.output_dir / name).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"safe_to_write": report["safe_to_write"], "changed_ranges": len(report["changes"]),
                      "preserved": len(report["preserved"]), "review_required": len(report["review_required"])}))
    return 0 if report["safe_to_write"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
