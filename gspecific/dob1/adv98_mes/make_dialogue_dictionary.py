"""Build a dialogue dictionary for Dead of the Brain ADV98 MES files.

This is intentionally separate from the legacy ``tools_analysis`` utility.
Modern ``*_lang.json`` files carry their canonical source in ``original`` and
the editable result in ``translation``; macro braces are preserved verbatim.
If one source maps to multiple distinct translations, it is also written to
``annoying.json`` for manual review.
"""
import argparse
import json
from pathlib import Path

from rich.console import Console


def add_pair(dictionary: dict, original: str, translation: str, reference: str) -> None:
    if not isinstance(original, str) or not original.strip():
        return
    if not isinstance(translation, str) or not translation.strip():
        return
    entry = dictionary.setdefault(
        original,
        {"count": 0, "reference": 0, "translated": [], "references": []},
    )
    entry["reference"] += 1
    entry["references"].append(reference)
    if translation not in entry["translated"]:
        entry["translated"].append(translation)
        entry["count"] = len(entry["translated"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=int, default=2, help="workspace number (default: 2)")
    parser.add_argument("--workspace-dir", type=Path, help="explicit workspace directory")
    args = parser.parse_args()
    console = Console()
    base = args.workspace_dir or Path(f"C:/work_han/workspace{args.workspace}")
    script_dir = base / "script-pc98" / "MES"
    dictionary = {}
    files = 0
    groups = 0
    translated_groups = 0
    paths = sorted(script_dir.glob("*_lang.json"))
    total_files = len(paths)
    for file_index, path in enumerate(paths, 1):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            console.print(f"ERROR {path.name}: {exc}", style="red")
            continue
        dialogue_groups = data.get("dialogue_groups") if isinstance(data, dict) else None
        if not isinstance(dialogue_groups, list):
            continue
        files += 1
        file_groups = 0
        file_translated = 0
        for group in dialogue_groups:
            if not isinstance(group, dict):
                continue
            groups += 1
            file_groups += 1
            if isinstance(group.get("translation"), str) and group["translation"].strip():
                translated_groups += 1
                file_translated += 1
            add_pair(dictionary, group.get("original"), group.get("translation"), f"{path.name}:{group.get('id', '')}")
        file_percent = (file_translated / file_groups * 100) if file_groups else 100.0
        overall_percent = (translated_groups / groups * 100) if groups else 100.0
        console.print(
            f"{file_index}/{total_files} {path.name}: "
            f"{file_translated}/{file_groups} ({file_percent:.2f}%)"
        )
        console.print(
            f"  Total: {translated_groups}/{groups} ({overall_percent:.2f}%)",
            style="green" if overall_percent >= 100 else "yellow",
        )

    annoying = {key: value for key, value in dictionary.items() if value["count"] > 1}
    dictionary_path = base / "dictionary.json"
    annoying_path = base / "annoying.json"
    for path, payload in ((dictionary_path, dictionary), (annoying_path, annoying)):
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    console.print(f"MES files: {files}, dialogue groups: {groups}")
    overall_percent = (translated_groups / groups * 100) if groups else 100.0
    console.print(f"Total translation progress: {translated_groups}/{groups} ({overall_percent:.2f}%)")
    console.print(f"dictionary.json: {len(dictionary)} source keys")
    console.print(f"annoying.json: {len(annoying)} ambiguous source keys", style="yellow" if annoying else "green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
