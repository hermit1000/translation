"""Collect FQ2 translations that share identical Japanese text.

Usage: python -m gspecific.fq.fq2.make_dialogue_dictionary [workspace]
"""

import argparse
import json
from pathlib import Path

from gspecific.fq.fq2.common import DEFAULT_WORKSPACE, DISKS


def lang_paths(workspace):
    return [path for disk in DISKS
            for path in sorted((workspace / "script-pc98" / disk).glob("*_lang.json"))]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\r\n")


def build_dictionary(paths):
    dictionary = {}
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not document["format"].startswith("fq2-pc98-"):
            raise ValueError(f"unexpected language format: {path}")
        for entry in document["entries"]:
            item = dictionary.setdefault(entry["text"],
                                         {"count": 0, "reference": 0,
                                          "translated": [], "references": []})
            item["reference"] += 1
            item["references"].append(f"{path.parent.name}/{path.name}:{entry['id']}")
            translation = entry.get("translation", "")
            if translation not in item["translated"]:
                item["translated"].append(translation)
                item["count"] = len(item["translated"])
    return dictionary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=DEFAULT_WORKSPACE)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    dictionary = build_dictionary(lang_paths(workspace))
    conflicts = {text: {"translated": item["translated"],
                        "references": item["references"]}
                 for text, item in dictionary.items() if item["count"] > 1}
    write_json(workspace / "dictionary.json", dictionary)
    write_json(workspace / "annoying.json", conflicts)
    print(f"{len(dictionary)} source texts; {len(conflicts)} conflicts")


if __name__ == "__main__":
    main()
