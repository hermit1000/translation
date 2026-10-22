"""Collect all Disk A/B *_lang.json translations by identical source text.

Usage: python -m gspecific.fq.fq1.make_dialogue_dictionary
"""

import argparse
import json
from pathlib import Path


DEFAULT_WORKSPACE = Path("C:/work_han/workspace11")
EQUIVALENT_SERIFU_IDS = (12, 91, 120, 150, 182, 183)


def canonical_serifu_texts(paths):
    source = next(path for path in paths if path.parent.name == "Disk_A"
                  and path.name == "SERIFU_lang.json")
    entries = json.loads(source.read_text(encoding="utf-8"))["entries"]
    return {number: entries[number]["text"] for number in EQUIVALENT_SERIFU_IDS}


def source_key(path, entry, canonical_texts):
    if (path.parent.name == "Disk_B" and path.name == "SERIFU_lang.json"
            and entry["id"] in canonical_texts):
        return canonical_texts[entry["id"]]
    return entry["text"]
def lang_paths(workspace):
    return [path for letter in "AB"
            for path in sorted((workspace / f"script-pc98/Disk_{letter}").glob("*_lang.json"))]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\r\n")


def build_dictionary(paths):
    dictionary = {}
    canonical_texts = canonical_serifu_texts(paths)
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not document.get("format", "").startswith("fq1-pc98-"):
            raise ValueError(f"unexpected lang format: {path}")
        for entry in document["entries"]:
            original = source_key(path, entry, canonical_texts)
            translation = entry.get("translation", "")
            item = dictionary.setdefault(original, {"count": 0, "reference": 0,
                                                    "translated": [], "references": [],
                                                    "source_variants": []})
            item["reference"] += 1
            item["references"].append(f"{path.parent.name}/{path.name}:{entry['id']}")
            if entry["text"] not in item["source_variants"]:
                item["source_variants"].append(entry["text"])
            if translation not in item["translated"]:
                item["translated"].append(translation)
                item["count"] = len(item["translated"])
    return dictionary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    dictionary = build_dictionary(lang_paths(workspace))
    conflicts = {original: {"translated": item["translated"],
                            "references": item["references"],
                            "source_variants": item["source_variants"]}
                 for original, item in dictionary.items() if item["count"] > 1}
    write_json(workspace / "dictionary.json", dictionary)
    write_json(workspace / "annoying.json", conflicts)
    print(f"{len(dictionary)} source texts; {len(conflicts)} conflicts")


if __name__ == "__main__":
    main()
