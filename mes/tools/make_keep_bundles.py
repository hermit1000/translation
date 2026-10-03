"""Create bundles for groups containing @keep entries, including group context."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def entries_in_order(data: dict) -> list[dict]:
    return list(data.get("dialogue_groups", [])) + list(data.get("overlay_texts", []))


def is_keep(entry: dict) -> bool:
    return entry.get("translation") == "@keep" or entry.get("status") == "passed"


def collect_keep_groups(mes_dir: Path) -> list[tuple[Path, str, list[dict]]]:
    result = []
    for source_path in sorted(mes_dir.glob("*_lang.json")):
        if source_path.name.lower().startswith("main"):
            continue
        data = load_json(source_path)
        grouped: dict[str, list[dict]] = {}
        order: list[str] = []
        for entry in entries_in_order(data):
            group = entry.get("display_group") or f"offset:{entry['offset']}"
            if group not in grouped:
                grouped[group] = []
                order.append(group)
            grouped[group].append(entry)
        for group in order:
            members = grouped[group]
            if any(is_keep(entry) for entry in members):
                result.append((source_path, group, members))
    return result


def make_keep_bundles(mes_dir: Path, output_dir: Path, target: int, maximum: int) -> list[Path]:
    groups = collect_keep_groups(mes_dir)
    total_entries = sum(len(members) for _, _, members in groups)
    bundle_count = max(1, (total_entries + target - 1) // target) if groups else 0
    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.glob("translation_keep_bundle_*.json"):
        old.unlink()

    result = []
    group_index = 0
    for number in range(1, bundle_count + 1):
        remaining_entries = sum(len(members) for _, _, members in groups[group_index:])
        bundles_left = bundle_count - number + 1
        desired = max(1, round(remaining_entries / bundles_left))
        selected: list[tuple[Path, str, list[dict]]] = []
        count = 0
        while group_index < len(groups):
            candidate = groups[group_index]
            size = len(candidate[2])
            if selected and count >= desired:
                break
            if selected and count + size > maximum:
                break
            selected.append(candidate)
            count += size
            group_index += 1
        entries = []
        source_files = []
        for source_path, _group, members in selected:
            if source_path.name not in source_files:
                source_files.append(source_path.name)
            for entry in members:
                entries.append({
                    "source_file": source_path.name,
                    "source_path": str(source_path),
                    "id": entry.get("id"),
                    "offset": entry["offset"],
                    "display_group": entry.get("display_group"),
                    "display_role": entry.get("display_role"),
                    "display_line_index": entry.get("display_line_index"),
                    "original": entry.get("original", ""),
                    "translation": entry.get("translation", ""),
                    "status": entry.get("status", ""),
                    "keep_entry": is_keep(entry),
                })
        path = output_dir / f"translation_keep_bundle_{number:03d}.json"
        path.write_text(json.dumps({
            "format": "necronomicon-translation-bundle-v1",
            "bundle_kind": "keep-context",
            "bundle_number": number,
            "bundle_count": bundle_count,
            "source_files": source_files,
            "group_count": len(selected),
            "entry_count": len(entries),
            "display_groups": [group for _, group, _ in selected],
            "entries": entries,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result.append(path)
    if group_index != len(groups):
        raise RuntimeError("not all @keep groups were assigned to bundles")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mes-dir", type=Path, default=Path.cwd() / "MES")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    parser.add_argument("--target", type=int, default=125)
    parser.add_argument("--maximum", type=int, default=150)
    args = parser.parse_args()
    paths = make_keep_bundles(args.mes_dir, args.output_dir, args.target, args.maximum)
    print(f"created_keep_bundles={len(paths)} keep_context_entries={sum(load_json(p)['entry_count'] for p in paths)}")


if __name__ == "__main__":
    main()
