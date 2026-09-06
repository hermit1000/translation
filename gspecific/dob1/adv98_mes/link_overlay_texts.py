"""Prepare DOB1 overlay connection metadata from complete source MES records."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from .decode_mes import decode_mes, make_readable_records


def annotate_connections(source: bytes, info: dict, lang: dict, catalog: dict) -> None:
    if hashlib.sha256(source).hexdigest() != info["source_sha256"]:
        raise ValueError("source MES SHA-256 mismatch")
    groups = {group["id"]: group for group in lang.get("dialogue_groups", [])}
    references = {
        identifier: {"id": identifier, "offset": identifier.split(":", 1)[1]}
        for identifier in groups
    }
    ranges = []
    for dialogue in info.get("dialogues", []):
        if dialogue["id"] in groups:
            for segment in dialogue.get("segments", []):
                ranges.append((int(segment["offset"], 16), int(segment["end"], 16), dialogue["id"]))
    overlays = lang.get("overlay_texts", [])
    for overlay in overlays:
        identifier = overlay.get("id", "overlay:" + overlay["offset"])
        references[identifier] = {"id": identifier, "offset": overlay["offset"]}
        ranges.append((int(overlay["offset"], 16), int(overlay.get("end", overlay["offset"]), 16), identifier))

    neighbors = {identifier: set() for identifier in references}
    previous: set[str] = set()
    for record in make_readable_records(decode_mes(source)):
        if record["type"] == "text":
            start, end = int(record["offset"], 16), int(record["end"], 16)
            owners = {identifier for left, right, identifier in ranges if left <= end and start <= right}
            for identifier in owners:
                for other in (owners | previous) - {identifier}:
                    neighbors[identifier].add(other)
                    neighbors[other].add(identifier)
            previous = owners
        elif record.get("name") == "CALL_BUILTIN":
            args = record.get("arguments", [])
            slot = f'{args[0]["value"]:02X}' if len(args) == 1 and isinstance(args[0].get("value"), int) else None
            category = catalog.get(slot, {}).get("category")
            if category not in {"punctuation", "spacing"} and not (
                slot == "03" and catalog.get(slot, {}).get("name") == "MESSAGE_UI_SETUP"
            ):
                previous = set()
        else:
            previous = set()

    for overlay in overlays:
        identifier = overlay.get("id", "overlay:" + overlay["offset"])
        visited = {identifier}
        pending = [identifier]
        while pending:
            for other in neighbors[pending.pop()] - visited:
                visited.add(other)
                pending.append(other)
        overlay["connections"] = [
            references[other]
            for other in sorted(visited - {identifier}, key=lambda key: (int(references[key]["offset"], 16), key))
        ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path, help="stage annotated JSON files here")
    args = parser.parse_args()
    package = Path(__file__).parent
    base_catalog = json.loads((package / "macro_catalog.json").read_text(encoding="utf-8"))["macros"]
    overrides = json.loads((package / "file_macro_overrides.json").read_text(encoding="utf-8"))
    paths = sorted((args.workspace / "script-pc98" / "MES").glob("*_lang.json"))
    if not paths:
        raise ValueError("no MES language JSON files found")
    prepared = []
    linked = multiple = total = 0
    for path in paths:
        raw = path.read_bytes()
        lang = json.loads(raw.decode("utf-8"))
        if lang.get("format") != "dob1-adv98-mes-lang-v1":
            raise ValueError(f"unexpected format: {path}")
        info = json.loads(path.with_name(lang["source_info"]).read_text(encoding="utf-8"))
        stem = path.name.removesuffix("_lang.json")
        catalog = copy.deepcopy(base_catalog)
        for mapping in (info.get("macro_overrides", {}), overrides.get(stem, {})):
            for slot, values in mapping.items():
                catalog[slot] = {**catalog.get(slot, {}), **values}
        source = (args.workspace / "jpn-pc98" / "MES" / stem).read_bytes()
        annotate_connections(source, info, lang, catalog)
        for overlay in lang.get("overlay_texts", []):
            total += 1
            linked += bool(overlay["connections"])
            multiple += len(overlay["connections"]) > 1
        prepared.append((path.name, raw, lang))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, raw, lang in prepared:
        destination = args.output_dir / name
        text = json.dumps(lang, ensure_ascii=False, indent=2) + "\n"
        destination.write_text(text.replace("\n", "\r\n"), encoding="utf-8", newline="")
        manifest.append({"file": name, "before_sha256": hashlib.sha256(raw).hexdigest(), "after_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})
    report = {"files": len(paths), "overlays": total, "linked_overlays": linked, "multiple_connections": multiple, "manifest": manifest}
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2).replace("\n", "\r\n") + "\r\n", encoding="utf-8", newline="")
    print(json.dumps({key: value for key, value in report.items() if key != "manifest"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
