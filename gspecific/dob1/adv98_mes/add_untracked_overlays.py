"""Add high-confidence untracked MES text candidates to lang overlay lists."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


DEFAULT_REVIEW_ORIGINALS = {"銃"}
DEFAULT_INFO_TRANSLATIONS = {
    "キャンセル": "취소",
    "そうなると警官の家族の人は凄く心配するだろうな": "그러면 경찰 가족들은 몹시 걱정하겠군",
    "どこの警察署にも国旗があるが": "어느 경찰서에나 국기가 있지만",
    "何に使われるのかは判らない": "무슨 용도인지는 모르겠다",
    "ここで一服していきたいが": "여기서 담배 한 대 피우고 싶지만",
    "シーラ達が待ってるからゆっくりはしてられない": "실라 일행이 기다리니 느긋하게 있을 수는 없어",
    "俺は絵の事が全然判らない": "난 그림에 관해서는 전혀 몰라",
    "一度だけ美術館へ行った事があるが": "한 번 미술관에 간 적이 있지만",
    "時間が経つにつれてどれも同じ絵に見えてくる": "시간이 지날수록 모두 같은 그림으로 보여",
    "さすがに俺は": "아무리 나라도",
    "これを持って歩き回る程の体力はない": "이걸 들고 돌아다닐 체력은 없어",
    "かなり残酷なやり方だが": "상당히 잔혹한 방법이지만",
    "一番安全なやり方でもあるからな": "가장 안전한 방법이기도 하니까",
    "下半身がないという事は": "하반신이 없다는 건",
    "既に喰ってしまったのか": "이미 먹어 버린 건가",
    "きっと工事に使われていたのだろう": "분명 공사에 쓰였겠지",
    "この箱には何が入っているんだい": "이 상자에는 뭐가 들어 있지",
    "〔まずいな": "〔큰일이군",
    "どうしてこんな事に": "어쩌다 이런 일이",
}


def default_workspace() -> Path:
    current = Path.cwd()
    if (current / "script-pc98" / "MES").is_dir():
        return current
    return Path(r"C:\work_han\workspace2")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=default_workspace())
    parser.add_argument(
        "--report",
        type=Path,
        help="candidate report (default: <workspace>/untracked_mes_text_candidates.json)",
    )
    parser.add_argument(
        "--include-review-multichar",
        action="store_true",
        help="also add review candidates whose trimmed original is at least two characters",
    )
    parser.add_argument(
        "--include-trimmed-original",
        action="append",
        default=[],
        help="also add a review candidate matching this trimmed original",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    mes_dir = workspace / "script-pc98" / "MES"
    report_path = (
        args.report or workspace / "untracked_mes_text_candidates.json"
    ).resolve()
    if not report_path.is_file():
        parser.error(f"candidate report not found: {report_path}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    by_file: dict[str, list[tuple[str, dict[str, object], str]]] = defaultdict(list)
    included_originals = DEFAULT_REVIEW_ORIGINALS | set(args.include_trimmed_original)
    for candidate in report.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        original = candidate.get("original")
        if not isinstance(original, str):
            continue
        selected = candidate.get("confidence") == "high" or (
            args.include_review_multichar and len(original.strip()) > 1
        ) or original.strip() in included_originals
        if not selected:
            continue
        for occurrence in candidate.get("occurrences", []):
            if isinstance(occurrence, dict) and occurrence.get("file"):
                by_file[str(occurrence["file"])].append((original, occurrence, ""))

    # Some common menu labels are not adjacent to the slot-03 calls used by
    # the candidate report.  Collect these known display literals directly
    # from info records so they cannot silently remain untranslated.
    for info_path in sorted(mes_dir.glob("*_info.json")):
        stem = info_path.name.removesuffix("_info.json")
        info = json.loads(info_path.read_text(encoding="utf-8"))
        for record in info.get("records", []):
            if not isinstance(record, dict) or record.get("type") != "text":
                continue
            original = record.get("original")
            if not isinstance(original, str):
                continue
            translation = DEFAULT_INFO_TRANSLATIONS.get(original.strip())
            if translation is not None:
                by_file[stem] = [
                    item
                    for item in by_file[stem]
                    if item[1].get("offset") != record.get("offset")
                ]
                by_file[stem].append((original, record, translation))

    changed_files = 0
    added = 0
    for stem, candidates in sorted(by_file.items()):
        lang_path = mes_dir / f"{stem}_lang.json"
        info_path = mes_dir / f"{stem}_info.json"
        if not lang_path.is_file() or not info_path.is_file():
            raise SystemExit(f"missing info/lang for {stem}")
        lang = json.loads(lang_path.read_text(encoding="utf-8"))
        info = json.loads(info_path.read_text(encoding="utf-8"))
        records = {
            record.get("offset"): record
            for record in info.get("records", [])
            if isinstance(record, dict)
        }
        overlays = lang.setdefault("overlay_texts", [])
        existing = {
            overlay.get("offset"): overlay
            for overlay in overlays
            if isinstance(overlay, dict) and overlay.get("offset")
        }
        file_added = 0
        for original, occurrence, translation in candidates:
            offset = occurrence.get("offset")
            if offset in existing:
                overlay = existing[offset]
                if translation and not overlay.get("translation"):
                    overlay["translation"] = translation
                    overlay["status"] = "pending"
                    file_added += 1
                continue
            record = records.get(offset)
            if not record or record.get("type") != "text":
                raise SystemExit(f"invalid candidate record: {stem} {offset}")
            if record.get("original") != original:
                raise SystemExit(f"stale candidate original: {stem} {offset}")
            overlays.append(
                {
                    "offset": offset,
                    "end": record.get("end"),
                    "original": original,
                    "translation": translation,
                    "status": "pending" if translation else "incomplete: untranslated overlay",
                }
            )
            existing[offset] = overlays[-1]
            file_added += 1
        if not file_added:
            continue
        overlays.sort(key=lambda overlay: int(overlay["offset"], 16))
        changed_files += 1
        added += file_added
        print(f"{stem}: {file_added}")
        if not args.dry_run:
            lang_path.write_text(
                json.dumps(lang, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    mode = "preview" if args.dry_run else "written"
    print(f"{mode}: added {added} overlay(s) in {changed_files} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
