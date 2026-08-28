"""Apply unambiguous dictionary translations to ADV98 MES language JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def default_workspace() -> Path:
    current = Path.cwd()
    if (current / "script-pc98" / "MES").is_dir():
        return current
    return Path(r"C:\work_han\workspace2")


def load_candidates(path: Path) -> dict[str, str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    candidates = {}
    for original, entry in document.items():
        if not isinstance(original, str) or not isinstance(entry, dict):
            continue
        translations = entry.get("translated")
        if not isinstance(translations, list):
            continue
        unique = list(
            dict.fromkeys(
                value
                for value in translations
                if isinstance(value, str) and value.strip()
            )
        )
        if len(unique) == 1:
            candidates[original] = unique[0]
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workspace",
        type=Path,
        nargs="?",
        default=default_workspace(),
        help="workspace containing dictionary.json and script-pc98/MES (default: current workspace)",
    )
    parser.add_argument("--dictionary", type=Path, help="dictionary JSON path")
    parser.add_argument("--annoying", type=Path, help="manually resolved annoying JSON path")
    parser.add_argument(
        "--only-empty",
        action="store_true",
        help="fill only empty translations instead of updating different translations",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview changes without writing files",
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    dictionary_path = (args.dictionary or workspace / "dictionary.json").resolve()
    annoying_path = (args.annoying or workspace / "annoying.json").resolve()
    mes_dir = workspace / "script-pc98" / "MES"
    if not dictionary_path.is_file():
        parser.error(f"dictionary not found: {dictionary_path}")
    paths = sorted(mes_dir.glob("*_lang.json"))
    if not paths:
        parser.error(f"no *_lang.json files found: {mes_dir}")

    candidates = load_candidates(dictionary_path)
    resolved_annoying = {}
    if annoying_path.is_file():
        resolved_annoying = load_candidates(annoying_path)
        candidates.update(resolved_annoying)
    changed_files = 0
    changed_groups = 0
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        file_changes = 0
        for section in ("dialogue_groups", "overlay_texts"):
            for group in document.get(section, []):
                if not isinstance(group, dict):
                    continue
                candidate = candidates.get(group.get("original"))
                current = group.get("translation")
                if candidate is None or current == candidate:
                    continue
                if args.only_empty and isinstance(current, str) and current.strip():
                    continue
                group["translation"] = candidate
                group["status"] = "pending"
                file_changes += 1

        if not file_changes:
            continue
        changed_files += 1
        changed_groups += file_changes
        print(f"{path.name}: {file_changes}")
        if not args.dry_run:
            path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    mode = "preview" if args.dry_run else "written"
    print(
        f"{mode}: {changed_groups} dialogue/overlay entry(s) in {changed_files} file(s); "
        f"applicable entries: {len(candidates)} "
        f"(resolved annoying entries: {len(resolved_annoying)})"
    )
    if args.dry_run and changed_groups:
        print("Run again without --dry-run to apply these changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
