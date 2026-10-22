"""Apply selected translations from annoying.json to FQ2 language JSON files.

Usage: python -m gspecific.fq.fq2.apply_dialogue_dictionary [--dry-run]
"""

import argparse
import json
from pathlib import Path

from gspecific.fq.fq2.common import DEFAULT_WORKSPACE, encoder
from gspecific.fq.fq2.make_dialogue_dictionary import lang_paths, write_json
from gspecific.fq.fq2.write_lang import encode_dialogue, encode_name


def selected_candidates(path):
    document = json.loads(path.read_text(encoding="utf-8"))
    candidates = {}
    for source, item in document.items():
        choices = item.get("translated")
        if not isinstance(choices, list):
            raise ValueError(f"invalid candidates: {source!r}")
        if len(choices) == 1 and isinstance(choices[0], str) and choices[0]:
            candidates[source] = choices[0]
    return candidates


def plan_updates(paths, candidates, encode, words):
    updates = []
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not document["format"].startswith("fq2-pc98-"):
            raise ValueError(f"unexpected language format: {path}")
        changed = []
        for entry in document["entries"]:
            translation = candidates.get(entry["text"])
            if translation is None or translation == entry.get("translation"):
                continue
            if path.name in ("UNIT_NAMES_lang.json", "CLASS_NAMES_lang.json"):
                raw = encode_name(translation, words)
            elif path.name == "SERIFU_lang.json":
                raw = encode_dialogue(translation, encode)
            else:
                raw = encode(translation)
            if path.name != "SERIFU_lang.json" and len(raw) >= entry["field_byte_length"]:
                raise ValueError(f"translation too long: {path}:{entry['id']}")
            entry["translation"] = translation
            entry["translation_byte_length"] = len(raw)
            changed.append(entry["id"])
        if changed:
            updates.append((path, document, changed))
    return updates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--dictionary", type=Path, help="default: workspace/annoying.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    dictionary = args.dictionary.resolve() if args.dictionary else workspace / "annoying.json"
    candidates = selected_candidates(dictionary)
    code_root = Path(__file__).resolve().parents[3]
    encode = encoder(code_root, workspace)
    words = json.loads((workspace / "script-pc98/custom_word.json").read_text(encoding="utf-8"))
    updates = plan_updates(lang_paths(workspace), candidates, encode, words)
    if not args.dry_run:
        for path, document, _ in updates:
            write_json(path, document)
    action = "would update" if args.dry_run else "updated"
    print(f"{action} {sum(len(ids) for _, _, ids in updates)} entries")
    for path, _, ids in updates:
        print(path, ids)


if __name__ == "__main__":
    main()
