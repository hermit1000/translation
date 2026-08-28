#!/usr/bin/env python3
"""Round-trip compare Korean MES bytes against *_lang.json translations."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
try:
    from .encode_mes_batch import split_by_info_segments
    from .translation_codec import load_font_codes, encode_translation
except ImportError:
    from encode_mes_batch import split_by_info_segments
    from translation_codec import load_font_codes, encode_translation

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument('workspace', nargs='?', type=Path, default=Path(r'C:\work_han\workspace2')); a=ap.parse_args()
    root=a.workspace.resolve(); d=root/'script-pc98'/'MES'; outdir=root/'kor-pc98'/'MES'
    codes=load_font_codes(Path(__file__).resolve().parents[3]/'font_table'/'font_table-kor-jin.json')
    checked=issues=0
    for lp in sorted(d.glob('*_lang.json')):
        stem=lp.name.removesuffix('_lang.json'); op=outdir/stem
        ip=d/f'{stem}_info.json'
        if not op.exists() or not ip.exists(): continue
        lang=json.loads(lp.read_text(encoding='utf-8')); info=json.loads(ip.read_text(encoding='utf-8')); data=op.read_bytes()
        records=info['records']; by={r['offset']:i for i,r in enumerate(records)}
        for g in lang.get('dialogue_groups',[]):
            meta=next((x for x in info.get('dialogues',[]) if x.get('id')==g.get('id')),None)
            if not meta: continue
            value=(g.get('translation') or '').replace('|','')
            if value.startswith('{') and '}' in value: value=value.split('}',1)[1]
            parts=split_by_info_segments(value,meta,records,by)
            cursor=0; ok=True
            marker_values=[m for m in re.findall(r"\{([^{}]*)\}", value)
                           if m in {',', '.', '!', '?', '‥', ' ' }]
            positions=[]
            for n,part in enumerate(parts):
                if not part: positions.append(None); continue
                raw=encode_translation(part,codes); pos=data.find(raw,cursor)
                if pos < 0:
                    print(f'FAIL {stem} {g.get("id")} segment={n+1} text={part!r}')
                    issues+=1; ok=False; break
                positions.append(pos)
                cursor=pos+len(raw)
            if ok:
                # Check each punctuation in the exact gap between its source
                # segments; searching the whole file would produce false
                # passes when the same glyph appears elsewhere.
                pi=0
                for mac in sorted(meta.get('macros', []), key=lambda x:int(x['offset'],16)):
                    if mac.get('slot') not in {'0D','0E','0F','11','12'}: continue
                    if pi >= len(marker_values): break
                    left=positions[min(pi+3, len(positions)-1)] if positions else None
                    right=positions[min(pi+4, len(positions)-1)] if positions else None
                    if left is not None:
                        end = right if right is not None else len(data)
                        if data.find(encode_translation(marker_values[pi],codes), left+1, end) < 0:
                            print(f'FAIL {stem} {g.get("id")} punctuation={marker_values[pi]!r}')
                            issues+=1; ok=False; break
                    pi+=1
            checked+=1
    print(f'checked dialogues: {checked}, mismatches: {issues}')
    return 1 if issues else 0
if __name__=='__main__': raise SystemExit(main())
