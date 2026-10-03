"""Merge cross-file translation bundles into their original *_lang.json files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def entries_in_order(data: dict) -> list[dict]:
    return list(data.get("dialogue_groups", [])) + list(data.get("overlay_texts", []))


def apply_bundle(path: Path, check_only: bool) -> int:
    bundle = load_json(path)
    if bundle.get("format") != "necronomicon-translation-bundle-v1":
        raise ValueError(f"unsupported bundle format: {path}")
    sources: dict[str, tuple[Path, dict[str, dict]]] = {}
    for source_file in bundle.get("source_files", []):
        source_path = Path(next(e["source_path"] for e in bundle["entries"] if e["source_file"] == source_file))
        data = load_json(source_path)
        sources[source_file] = (source_path, {e["offset"]: e for e in entries_in_order(data)})
    changed = 0
    seen: set[tuple[str, str]] = set()
    for item in bundle.get("entries", []):
        key = (item["source_file"], item["offset"])
        if key in seen:
            raise ValueError(f"duplicate entry {key} in {path}")
        seen.add(key)
        if item["source_file"] not in sources:
            raise ValueError(f"source file missing from bundle metadata: {key}")
        source_path, by_offset = sources[item["source_file"]]
        if item["offset"] not in by_offset:
            raise ValueError(f"offset not found in {source_path.name}: {item['offset']}")
        target = by_offset[item["offset"]]
        if target.get("original", "") != item.get("original", ""):
            raise ValueError(f"original mismatch at {source_path.name}:{item['offset']}")
        if target.get("display_group") != item.get("display_group"):
            raise ValueError(f"display_group mismatch at {source_path.name}:{item['offset']}")
        translation = item.get("translation", "")
        if not translation:
            continue
        status = item.get("status", "translated")
        if target.get("translation") != translation or target.get("status") != status:
            changed += 1
        if not check_only:
            target["translation"] = translation
            target["status"] = status
    if not check_only:
        touched = {source_file for source_file, _ in seen}
        for source_file in touched:
            source_path, _ = sources[source_file]
            data = load_json(source_path)
            by_offset = {e["offset"]: e for e in entries_in_order(data)}
            for item in bundle["entries"]:
                if item["source_file"] == source_file and item.get("translation"):
                    by_offset[item["offset"]]["translation"] = item["translation"]
                    by_offset[item["offset"]]["status"] = item.get("status", "translated")
            source_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle_dir", type=Path)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--file", type=Path, help="apply one explicit bundle file")
    parser.add_argument(
        "--translated",
        action="store_true",
        help="use *_translated.json bundle files instead of the original bundles",
    )
    args = parser.parse_args()
    if args.file:
        paths = [args.file]
    elif args.translated:
        paths = sorted(args.bundle_dir.glob("translation_bundle_*_translated.json"))
    else:
        paths = sorted(args.bundle_dir.glob("translation_bundle_*.json"))
        paths = [path for path in paths if not path.name.endswith("_translated.json")]
    changed = sum(apply_bundle(path, args.check_only) for path in paths)
    print(f"validated_bundles={len(paths)} changed_entries={changed} check_only={args.check_only}")


if __name__ == "__main__":
    main()
