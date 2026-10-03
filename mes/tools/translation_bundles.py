"""Create translation bundles and merge translated bundles into *_lang.json files."""

from __future__ import annotations

import argparse
from pathlib import Path

from apply_translation_bundles import apply_bundle
from make_translation_bundles import load_json, make_bundles
from make_keep_bundles import make_keep_bundles


def apply_bundles(bundle_dir: Path, check_only: bool, translated: bool) -> None:
    translated_paths = sorted(bundle_dir.glob("translation_bundle_*_translated.json"))
    if translated and translated_paths:
        paths = translated_paths
    else:
        paths = sorted(
            path
            for path in bundle_dir.glob("translation_bundle_*.json")
            if not path.name.endswith("_translated.json")
        )
    changed = sum(apply_bundle(path, check_only) for path in paths)
    print(f"validated_bundles={len(paths)} changed_entries={changed} check_only={check_only}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create translation bundles or apply translated bundles to the original JSON files."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    make_parser = subparsers.add_parser("make", help="create bundles from untranslated groups")
    make_parser.add_argument("--mes-dir", type=Path, default=Path.cwd() / "MES")
    make_parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    make_parser.add_argument("--target", type=int, default=125)
    make_parser.add_argument("--minimum", type=int, default=100)
    make_parser.add_argument("--maximum", type=int, default=150)

    keep_parser = subparsers.add_parser("make-keep", help="create @keep bundles with display-group context")
    keep_parser.add_argument("--mes-dir", type=Path, default=Path.cwd() / "MES")
    keep_parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    keep_parser.add_argument("--target", type=int, default=125)
    keep_parser.add_argument("--maximum", type=int, default=150)

    apply_parser = subparsers.add_parser("apply", help="apply *_translated.json files to original JSON files")
    apply_parser.add_argument("bundle_dir", type=Path, nargs="?", default=Path.cwd())
    apply_parser.add_argument("--check-only", action="store_true")
    apply_parser.add_argument("--file", type=Path, help="apply one explicit bundle file")
    apply_parser.add_argument(
        "--original",
        action="store_true",
        help="apply original translation_bundle_*.json files instead of *_translated.json files",
    )

    args = parser.parse_args()
    if args.command == "make":
        paths = make_bundles(args.mes_dir, args.output_dir, args.target, args.minimum, args.maximum)
        print(f"created_bundles={len(paths)} pending_entries_in_bundles={sum(load_json(p)['entry_count'] for p in paths)}")
    elif args.command == "make-keep":
        paths = make_keep_bundles(args.mes_dir, args.output_dir, args.target, args.maximum)
        print(f"created_keep_bundles={len(paths)} keep_context_entries={sum(load_json(p)['entry_count'] for p in paths)}")
    else:
        if args.file:
            changed = apply_bundle(args.file, args.check_only)
            print(f"validated_bundles=1 changed_entries={changed} check_only={args.check_only}")
        else:
            apply_bundles(args.bundle_dir, args.check_only, translated=not args.original)


if __name__ == "__main__":
    main()
