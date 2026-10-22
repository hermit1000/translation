"""Apply single selected candidates to every matching Disk A/B lang entry.

Edit annoying.json so each chosen translated list contains one string.
Usage: python -m gspecific.fq.fq1.apply_dialogue_dictionary [--dry-run]
"""

import argparse
import json
from pathlib import Path

from gspecific.fq.fq1.make_dialogue_dictionary import (
    DEFAULT_WORKSPACE, canonical_serifu_texts, lang_paths, source_key, write_json,
)
from gspecific.fq.fq1.write_lang import encoder, strip_serifu_wrap_spaces


def selected_candidates(path):
    document = json.loads(path.read_text(encoding="utf-8"))
    candidates = {}
    for original, item in document.items():
        values = item.get("translated")
        if not isinstance(values, list):
            raise ValueError(f"invalid candidates for {original!r}")
        if len(values) == 1 and isinstance(values[0], str) and values[0].strip():
            candidates[original] = values[0]
    return candidates


def plan_updates(paths, candidates, encode):
    updates = []
    canonical_texts = canonical_serifu_texts(paths)
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not document.get("format", "").startswith("fq1-pc98-"):
            raise ValueError(f"unexpected lang format: {path}")
        changed_ids = []
        for entry in document["entries"]:
            candidate = candidates.get(source_key(path, entry, canonical_texts))
            if candidate is None or entry.get("translation") == candidate:
                continue
            if (path.name == "SERIFU_EXTRA_lang.json" and entry.get("translation")
                    and entry["translation"].replace("|_", "_") == candidate.replace("|_", "_")):
                continue
            value = strip_serifu_wrap_spaces(candidate) if path.name == "SERIFU_lang.json" else candidate
            length = len(encode(value))
            if path.name == "CLASS_NAMES_lang.json" and length != entry["field_byte_length"]:
                raise ValueError(f"class name length: {path}:{entry['id']}")
            if path.name == "UNIT_NAMES_lang.json" and not 0 < length <= entry["field_byte_length"]:
                raise ValueError(f"unit name length: {path}:{entry['id']}")
            if path.name not in ("SERIFU_lang.json", "CLASS_NAMES_lang.json", "UNIT_NAMES_lang.json") and length > entry["byte_length"]:
                raise ValueError(f"fixed text too long: {path}:{entry['id']}")
            entry["translation"] = candidate
            entry["translation_byte_length"] = length
            changed_ids.append(entry["id"])
        if changed_ids:
            updates.append((path, document, changed_ids))
    return updates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--dictionary", type=Path, help="default: workspace/annoying.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    dictionary_path = args.dictionary.resolve() if args.dictionary else workspace / "annoying.json"
    candidates = selected_candidates(dictionary_path)
    code_root = Path(__file__).resolve().parents[3]
    updates = plan_updates(lang_paths(workspace), candidates, encoder(code_root))
    if not args.dry_run:
        for path, document, _ in updates:
            write_json(path, document)
    action = "would update" if args.dry_run else "updated"
    print(f"{action} {sum(len(ids) for _, _, ids in updates)} entries; "
          f"selected source dialogues: {len(candidates)}")
    for path, _, ids in updates:
        print(path, ids)


if __name__ == "__main__":
    main()
