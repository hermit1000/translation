"""Encode all MES files from *_info.json and *_lang.json translations."""
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile
import re
from rich.console import Console
from rich.table import Table
from pathlib import Path
from typing import Any
try:
    from .translation_codec import encode_translation, load_font_codes
except ImportError:
    from translation_codec import encode_translation, load_font_codes

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

PUNCT = {"0D": ",", "0E": "‥", "0F": ".", "10": " ", "11": "!", "12": "?"}
DISPLAY_LINE_CELLS = 31
CLOSING_PUNCTUATION = "》〉」』】〕〗〙〛）］)]”’"

def trim_wrap_boundary_spaces(value: str, width: int = DISPLAY_LINE_CELLS) -> str:
    """Remove literal spaces that would be the first blank after a full line."""
    # Opening hesitation marks belong directly to the following word when
    # they immediately follow a speaker label.
    value = re.sub(r'^(\{[^{}]*\}(?:\{‥\})+)[ \t]+', r'\1', value)
    speaker = re.match(r'^\{[^{}]*\}', value)
    if speaker:
        prefix, body = value[:speaker.end()], value[speaker.end():]
        leading = re.match(r'^(?:\{‥\})+', body)
        if leading:
            head, body_tail = body[:leading.end()], body[leading.end():]
        else:
            head, body_tail = '', body
        next_text = r'(?=[^{}\s' + re.escape(CLOSING_PUNCTUATION) + r'])'
        body_tail = re.sub(r'((?:\{‥\})+)' + next_text, r'\1 ', body_tail)
        value = prefix + head + body_tail
    out: list[str] = []
    cells = 0
    i = 0
    while i < len(value):
        if value[i] == "{" and "}" in value[i + 1:]:
            end = value.find("}", i + 1)
            token = value[i:end + 1]
            # A macro occupies the visible width of its displayed value;
            # punctuation/spacing macros are one cell, speaker labels retain
            # their short visible character count.
            visible = token[1:-1]
            cells += max(1, len(visible))
            out.append(token)
            i = end + 1
            continue
        ch = value[i]
        if ch == "|":
            # Editing-only separator; it has no display-cell width.
            out.append(ch)
            i += 1
            continue
        # ADV98 wraps at the editable positions 31, 61, ... (1-based).
        # Remove a literal space that would occupy the first cell after a
        # completed line, preserving the original boundary behavior.
        if ch == " " and cells > 0 and cells % (width - 1) == 0:
            i += 1
            continue
        out.append(ch)
        cells += 1
        i += 1
    return "".join(out)

def render_info_original(info: dict[str, Any], dialogue: dict[str, Any], catalog: dict[str, Any]) -> str:
    by_offset = {record.get("offset"): record for record in info.get("records", [])}
    offsets = [dialogue["id"].split(":", 1)[1]]
    offsets += [s["offset"] for s in dialogue.get("segments", [])]
    offsets += [m["offset"] for m in dialogue.get("macros", []) if m.get("offset")]
    result = []
    previous_type = None
    for offset in sorted(set(offsets), key=lambda value: int(value, 16)):
        record = by_offset.get(offset)
        if not record:
            continue
        if record.get("type") == "text":
            # Consecutive text records have no control-code boundary in the
            # source.  Keep that boundary visible in editable ``original``.
            if previous_type == "text":
                result.append("|")
            result.append(record.get("original", ""))
            previous_type = "text"
        elif record.get("type") == "command" and record.get("name") == "CALL_BUILTIN":
            macro = catalog.get(record.get("macro_slot", ""), {})
            if macro.get("category") in {"speaker", "punctuation", "spacing"}:
                result.append("{" + (macro.get("original") or macro.get("translation") or "") + "}")
            previous_type = "command"
    return "".join(result)

def validate_originals(stem: str, info: dict[str, Any], lang: dict[str, Any]) -> bool:
    catalog = json.loads(Path(__file__).with_name("macro_catalog.json").read_text(encoding="utf-8")).get("macros", {})
    for slot, values in info.get("macro_overrides", {}).items():
        catalog[slot] = {**catalog.get(slot, {}), **values}
    overrides = json.loads(Path(__file__).with_name("file_macro_overrides.json").read_text(encoding="utf-8"))
    for slot, values in overrides.get(stem, {}).items():
        catalog[slot] = {**catalog.get(slot, {}), **values}
    expected = {d.get("id"): render_info_original(info, d, catalog) for d in info.get("dialogues", [])}
    # ``|`` is an editing-only segment separator and is ignored when
    # comparing the canonical Japanese source reconstructed from info.
    errors = [(g.get("id"), expected[g.get("id")], g.get("original", "")) for g in lang.get("dialogue_groups", []) if g.get("id") in expected and g.get("original", "").replace("|", "") != expected[g.get("id")].replace("|", "")]
    if errors:
        print(f"ERROR {stem}: lang.original does not match info ({len(errors)} mismatch(es)); build stopped")
        for identifier, wanted, actual in errors:
            print(f"  id: {identifier}\n  info original: {wanted}\n  lang original: {actual}")
        return False
    return True

def split_by_info_segments(value: str, meta: dict[str, Any], records: list[dict[str, Any]], by_offset: dict[str, int]) -> list[str]:
    """Split a brace-marked translation using source macro positions."""
    text_segments = meta.get("segments", [])
    if len(text_segments) <= 1:
        return [re.sub(r"\{[^{}]*\}", "", value)]
    # Adjacent source text records can have no macro between them.  In that
    # case translators may use an explicit pipe as an editing-only boundary.
    # A group can also contain both kinds of boundary (e.g. punctuation
    # between the first two records and a pipe between the latter two), so do
    # not blindly split on pipes; consume source macro boundaries and pipes in
    # their original order.
    if "|" in value:
        tokens = list(re.finditer(r"\{[^{}]*\}|\|", value))
        # The first brace token is the speaker label and is not one of the
        # source macro boundaries.  Exclude it from the macro cursor; keeping
        # it here shifts every punctuation boundary by one token.
        macro_tokens = [
            m for m in tokens
            if m.group(0) != "|" and m.start() != 0
        ]
        macro_offsets = sorted((m.get("offset") for m in meta.get("macros", []) if m.get("offset")), key=lambda x: int(x, 16))
        pieces, start_pos, macro_pos, pipe_pos = [], 0, 0, 0
        prev_end = int(text_segments[0].get("end", text_segments[0]["offset"]), 16)
        for seg_index in range(len(text_segments) - 1):
            next_start = int(text_segments[seg_index + 1]["offset"], 16)
            needed = sum(prev_end <= int(off, 16) < next_start for off in macro_offsets)
            cut = None
            if needed:
                macro_pos += needed
                if macro_pos <= len(macro_tokens):
                    cut = macro_tokens[macro_pos - 1].end()
            else:
                while pipe_pos < len(tokens) and tokens[pipe_pos].start() < start_pos:
                    pipe_pos += 1
                while pipe_pos < len(tokens) and tokens[pipe_pos].group(0) != "|":
                    pipe_pos += 1
                if pipe_pos < len(tokens):
                    cut = tokens[pipe_pos].start()
                    pipe_pos += 1
            if cut is None:
                break
            pieces.append(re.sub(r"\{[^{}]*\}", "", value[start_pos:cut]))
            start_pos = cut
            if start_pos < len(value) and value[start_pos] == "|":
                start_pos += 1
            prev_end = int(text_segments[seg_index + 1].get("end", text_segments[seg_index + 1]["offset"]), 16)
        pieces.append(re.sub(r"\{[^{}]*\}", "", value[start_pos:]))
        return pieces
    macro_offsets = sorted((m.get("offset") for m in meta.get("macros", []) if m.get("offset")), key=lambda x: int(x, 16))
    all_macros = macro_offsets
    boundaries = []
    for index in range(len(text_segments) - 1):
        next_offset = text_segments[index + 1]["offset"]
        # ``meta.macros`` excludes the speaker command, so all macros before
        # the next text segment participate in the marker boundary count.
        preceding = [offset for offset in all_macros if int(offset, 16) < int(next_offset, 16)]
        if preceding:
            boundaries.append(len(preceding) - 1)
    matches = list(re.finditer(r"\{[^{}]*\}", value))
    # The leading speaker marker is not a punctuation boundary.  Exclude it
    # from the marker index list while retaining it in the first slice (it is
    # removed by the brace-stripping below).
    if matches and matches[0].start() == 0:
        matches = matches[1:]
    cuts = [matches[index].end() for index in boundaries if index < len(matches)]
    parts, start_pos = [], 0
    for cut in cuts:
        parts.append(re.sub(r"\{[^{}]*\}", "", value[start_pos:cut]))
        start_pos = cut
    parts.append(re.sub(r"\{[^{}]*\}", "", value[start_pos:]))
    return parts

def is_structural_literal(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and all(ch in "《》〔〕「」『』【】" for ch in stripped)

def load_json_checked(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR JSON parse failed: {path}")
        print(f"  line {exc.lineno}, column {exc.colno}, character {exc.pos}: {exc.msg}")
        return None

PUNCT = {"0D": ",", "0E": "‥", "0F": ".", "10": " ", "11": "!", "12": "?"}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", nargs="?", type=Path, default=Path(r"C:\work_han\workspace2"))
    ap.add_argument("--no-dosbox-x", action="store_true")
    ap.add_argument("--debug-offset", help="trace one source offset in 000046.MES")
    a = ap.parse_args(); root=a.workspace.resolve(); d=root/'script-pc98'/'MES'
    console = Console(); results = []
    font_path = Path(__file__).resolve().parents[3] / "font_table" / "font_table-kor-jin.json"
    font_codes = load_font_codes(font_path)
    for lang_path in sorted(d.glob('*_lang.json')):
        stem=lang_path.name.removesuffix('_lang.json'); info_path=d/f'{stem}_info.json'
        info=load_json_checked(info_path); lang=load_json_checked(lang_path)
        if info is None or lang is None:
            return 1
        if not validate_originals(stem, info, lang):
            return 1
        records=info['records']; by_offset={r['offset']:i for i,r in enumerate(records)}
        groups=lang.get('dialogue_groups', [])
        overlays = lang.get('overlay_texts', [])
        invalid_offsets = set()
        dialogue_ranges = [
            (int(segment['offset'], 16), int(segment['end'], 16))
            for dialogue in info.get('dialogues', [])
            for segment in dialogue.get('segments', [])
        ]

        # Overlay text is emitted by ADV98 screen/control routines rather
        # than the dialogue-window speaker flow.  Keep it in a separate
        # editable section, but apply it to the same source records before
        # the temporary MES manifest is encoded.
        for overlay in overlays:
            offset = overlay.get('offset')
            index = by_offset.get(offset)
            overlay_start = int(offset, 16) if offset else None
            overlay_end = (
                int(records[index].get('end', offset), 16)
                if index is not None and offset
                else overlay_start
            )
            if overlay_start is not None and any(
                start <= overlay_end and overlay_start <= end
                for start, end in dialogue_ranges
            ):
                # Older info files sometimes merged a newly recovered text
                # record into an existing dialogue segment.  The overlay is
                # then only a diagnostic alias; replacing it separately would
                # create overlapping byte ranges.
                overlay['status'] = 'passed: covered by dialogue segment'
                continue
            if index is None or records[index].get('type') != 'text':
                overlay['status'] = f'error: unknown overlay record {offset}'
                continue
            if overlay.get('original', '') != records[index].get('original', ''):
                overlay['status'] = 'error: original mismatch'
                print(f"ERROR {stem} overlay {offset}: original mismatch")
                continue
            translation = overlay.get('translation')
            if translation in (None, ''):
                overlay['status'] = 'incomplete: untranslated overlay'
                continue
            try:
                encode_translation(translation, font_codes)
            except ValueError as exc:
                overlay['status'] = f'error: {exc}'
                continue
            records[index]['translation'] = translation
            overlay['status'] = 'passed'
        for group in groups:
            # Keep the editable JSON exactly as entered.  Wrap-boundary
            # spaces and editing-only separators are normalized only in this
            # local value immediately before MES encoding; otherwise a build
            # would rewrite the translation and later edits would inherit a
            # shifted/incorrect space.
            source_translation = group.get('translation') or ''
            # Editing-only segment separators do not occupy a display cell.
            # Remove them before wrap-boundary calculation; otherwise every
            # later boundary can shift by one or more cells.
            normalized_translation = source_translation.replace('|', '')
            normalized_translation = trim_wrap_boundary_spaces(normalized_translation)
            original_markers = re.findall(r'\{([^{}]*)\}', group.get('original', ''))
            translation_markers = re.findall(r'\{([^{}]*)\}', normalized_translation)
            japanese_marker = next((
                marker for marker in translation_markers
                if re.search(r'[ぁ-んァ-ヶ一-龯々〆ヵヶ、。・「」『』〈〉《》【】〔〕]', marker)
            ), None)
            if japanese_marker is not None:
                print(f"ERROR {stem} {group.get('id')}: Japanese text/code remains in marker ({{{japanese_marker}}})")
                group["status"] = f"error: Japanese text/code remains in marker ({{{japanese_marker}}})"
                continue
            if re.search(r'\{[.!?]\}[ \t]+$', normalized_translation):
                group["status"] = "error: trailing space after sentence-ending macro"
                print(f"ERROR {stem} {group.get('id')}: trailing space after sentence-ending macro")
                continue
            if len(original_markers) != len(translation_markers):
                print(f"ERROR {stem} {group.get('id')}: macro marker count mismatch ({len(original_markers)} != {len(translation_markers)})")
                group["status"] = f"error: macro marker count mismatch ({len(original_markers)} != {len(translation_markers)})"
                meta = next((d for d in info.get('dialogues', []) if d.get('id') == group.get('id')), None)
                if meta:
                    invalid_offsets.update(s['offset'] for s in meta.get('segments', []))
                continue
            start=group['id'].split(':',1)[1]; start_i=by_offset.get(start)
            if start_i is None: continue
            meta = next((d for d in info.get('dialogues', []) if d.get('id') == group.get('id')), None)
            segment_offsets = {s.get('offset') for s in (meta or {}).get('segments', [])}
            related_offsets = segment_offsets | {m.get('offset') for m in (meta or {}).get('macros', [])}
            related_offsets.discard(None)
            related_indices = [by_offset[offset] for offset in related_offsets if offset in by_offset]
            if not related_indices:
                continue
            end_i=max(related_indices)+1
            text_ids=[by_offset[s['offset']] for s in (meta or {}).get('segments', []) if s.get('offset') in by_offset]
            if not text_ids: continue
            value = normalized_translation
            # Japanese names may remain inside an otherwise translated Korean line.
            if re.search(r'[ぁ-んァ-ン一-龯]', value) and not re.search(r'[가-힣]', value):
                group["status"] = "error: translation contains no Korean text"
                continue
            if value.startswith('{') and '}' in value: value=value.split('}',1)[1]
            full_value = value
            markers = re.findall(r'\{([^{}]*)\}', full_value)
            if markers:
                # Keep editing-only pipes while determining source-segment
                # boundaries.  They are removed from ``normalized_translation``
                # only for final cell-length validation/encoding; deleting
                # them here would merge adjacent records and drop later text.
                # Apply wrap-boundary normalization to the same value used
                # for segment splitting; otherwise a removed 31/61-space
                # could be reintroduced from the unnormalized source string.
                split_translation = trim_wrap_boundary_spaces(source_translation)
                parts = split_by_info_segments(split_translation, meta or {}, records, by_offset)
                for n, idx in enumerate(text_ids):
                    records[idx]['translation'] = parts[n] if n < len(parts) else ''
                punct_markers = [m for m in markers if m in {',', '.', '?', '!', '‥', ' ' }]
                pi = 0
                for i in range(start_i, end_i):
                    r = records[i]
                    if r.get('type') == 'command' and r.get('macro_slot') in PUNCT and pi < len(punct_markers):
                        r['translation'] = punct_markers[pi]; pi += 1
                status = "passed"
                for idx in text_ids:
                    translated = records[idx].get("translation")
                    if translated in (None, "") or (translated == records[idx].get("original") and not is_structural_literal(translated)):
                        status = f"incomplete: untranslated segment {records[idx].get('offset')}"
                        break
                    try:
                        encode_translation(translated, font_codes)
                    except ValueError as exc:
                        status = f"error: {exc}"
                        break
                # Some legacy groups intentionally merge adjacent source text
                # records into one Korean sentence.  If the editable value is
                # fully Korean, do not report an empty split fragment as an
                # untranslated segment.
                if status.startswith("incomplete") and re.search(r"[가-힣]", full_value) and not re.search(r"[ぁ-んァ-ン一-龯]", full_value):
                    status = "passed"
                group["status"] = status
                continue
            ti=0
            for i in range(start_i,end_i):
                r=records[i]; slot=r.get('macro_slot')
                if r.get('type')=='command' and slot in PUNCT:
                    candidates = [PUNCT[slot]]
                    if slot == '0F': candidates = ['?', '.', '!']
                    ch, pos = next(((c, value.find(c)) for c in candidates if value.find(c) >= 0), (PUNCT[slot], -1))
                    if pos>=0:
                        if ti < len(text_ids):
                            records[text_ids[ti]]['translation']=value[:pos]; ti+=1
                        else:
                            records[text_ids[-1]]['translation']=value[:pos]
                        r['translation']=ch; value=value[pos+len(ch):]
                elif r.get('type')=='text' and i==text_ids[-1]:
                    r['translation']=value
            if len(text_ids) > 1:
                chunks = re.split(r'([.!?])', full_value)
                text_chunks = chunks[0::2]
                for n, idx in enumerate(text_ids):
                    records[idx]['translation'] = text_chunks[n] if n < len(text_chunks) else ''
            info['records']=records
            status = "passed"
            for idx in text_ids:
                translated = records[idx].get("translation")
                if translated in (None, "") or (translated == records[idx].get("original") and not is_structural_literal(translated)):
                    status = f"incomplete: untranslated segment {records[idx].get('offset')}"
                    break
                try:
                    encode_translation(translated, font_codes)
                except ValueError as exc:
                    status = f"error: {exc}"
                    break
            if status.startswith("incomplete") and re.search(r"[가-힣]", full_value) and not re.search(r"[ぁ-んァ-ン一-龯]", full_value):
                status = "passed"
            group["status"] = status
        # Persist per-dialogue build status even if a later file fails.
        lang_path.write_text(json.dumps(lang, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        dialogue_offsets = {s['offset'] for d in info.get('dialogues', []) for s in d.get('segments', [])}
        overlay_offsets = {o.get('offset') for o in overlays if o.get('offset')}
        # The decoder can emit the same text range twice when both compressed
        # and Shift-JIS interpretations are valid.  It is one display cell,
        # so count each (offset,end) range once in coverage/status reporting.
        unique_map = {}
        for r in records:
            key = (r.get('offset'), r.get('end'))
            if r.get('type') != 'text':
                continue
            if r.get('offset') in invalid_offsets:
                continue
            if dialogue_offsets and r.get('offset') not in dialogue_offsets and r.get('offset') not in overlay_offsets:
                continue
            # Keep the last duplicate, matching by_offset's encoding target.
            unique_map[key] = r
        unique_text = list(unique_map.values())
        total = len(unique_text)
        translated = sum(1 for r in unique_text if r.get('translation') not in (None, r.get('original')) or is_structural_literal(r.get('translation') or r.get('original', '')))
        coverage = (translated / total * 100) if total else 100.0
        if coverage < 100:
            group_by_offset = {s.get("offset"): d.get("id") for d in info.get("dialogues", []) for s in d.get("segments", [])}
            missing = [r for r in unique_text if r.get("offset") in dialogue_offsets and r.get("translation") in (None, r.get("original")) and not is_structural_literal(r.get("translation") or r.get("original", ""))]
            print(f"INCOMPLETE {stem}: {len(missing)} untranslated segment(s)")
            for record in missing:
                print(f"  {group_by_offset.get(record.get('offset'), 'unknown')} @ {record.get('offset')}: {record.get('original', '')}")
        group_errors = [g for g in groups if str(g.get("status", "")).startswith("error")]
        group_incomplete = [g for g in groups if str(g.get("status", "")).startswith("incomplete")]
        if group_errors:
            results.append((stem, translated, total, coverage, f"failed: {len(group_errors)} dialogue error(s)"))
            continue
        # Any incomplete dialogue group keeps the file incomplete, even when
        # record coverage rounds to 100%.
        if group_incomplete:
            results.append((stem, translated, total, coverage,
                            f"incomplete: {len(group_incomplete)} dialogue group(s)"))
        else:
            results.append((stem, translated, total, coverage,
                            'ready' if coverage >= 100 else 'incomplete'))
        # Preserve manually indexed text blocks that are stored only in the
        # language document (for example ungrouped late-scene records).
        # encode_mes.py consumes the merged temporary document, so omitting
        # this field silently leaves those blocks in Japanese.
        if lang.get('extra_texts'):
            info['extra_texts'] = lang['extra_texts']
        if lang.get('credit_layout'):
            info['credit_layout'] = lang['credit_layout']
        with tempfile.NamedTemporaryFile('w',suffix='.json',delete=False,encoding='utf-8') as f:
            json.dump(info,f,ensure_ascii=False,indent=2); tmp=f.name
        source=root/'jpn-pc98'/'MES'/stem; output=root/'kor-pc98'/'MES'/stem
        try:
            cmd=[sys.executable,'-m','gspecific.dob1.adv98_mes.encode_mes',str(source),tmp,str(output),'font_table/font_table-kor-jin.json']
            if a.debug_offset and stem == '000046.MES': cmd += ['--debug-offset', a.debug_offset]
            subprocess.run(cmd,check=True)
        except subprocess.CalledProcessError as exc:
            results[-1] = (stem, translated, total, coverage, 'failed: font/translation')
            continue
        if not a.no_dosbox_x:
            dest=root/'kor-pc98-dosbox-x'/'MES'/stem; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(output.read_bytes())
    table = Table(title='ADV98 MES Build Progress')
    table.add_column('File'); table.add_column('Progress', justify='right'); table.add_column('Coverage', justify='right'); table.add_column('Status')
    for stem, translated, total, coverage, status in results:
        # Incomplete files require the same attention as failed files, so show
        # them in red in the progress table as well.
        style = 'green' if status == 'ready' else ('red' if status.startswith(('failed', 'incomplete')) else 'yellow')
        table.add_row(stem, f'{translated}/{total}', f'{coverage:.2f}%', status, style=style)
    total_translated = sum(item[1] for item in results)
    total_segments = sum(item[2] for item in results)
    total_coverage = (100.0 * total_translated / total_segments) if total_segments else 0.0
    failed_count = sum(1 for item in results if item[4].startswith('failed'))
    incomplete_count = sum(1 for item in results if item[4].startswith('incomplete'))
    if failed_count:
        total_status, total_style = f'failed: {failed_count} file(s)', 'red'
    elif incomplete_count:
        total_status, total_style = f'incomplete: {incomplete_count} file(s)', 'red'
    else:
        total_status, total_style = 'ready', 'green'
    table.add_section()
    table.add_row('TOTAL', f'{total_translated}/{total_segments}', f'{total_coverage:.2f}%', total_status, style=total_style)
    console.print(table)
    return 0
if __name__=='__main__': raise SystemExit(main())
