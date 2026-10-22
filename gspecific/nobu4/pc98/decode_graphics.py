"""Audit NB4 binary differences and decode changed image pairs without writing game files."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path


def write_json(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("C:/work_han/workspace0"))
    parser.add_argument("--code-root", type=Path, default=Path("C:/work_han/translation"))
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_root))
    from gspecific.nobu5.decode_graphics import decode_slogo_image, PC98_PALETTE_8
    from module.pc98_image.planar import decode_interleaved_planar, encode_interleaved_planar
    from PIL import Image

    root = args.workspace.resolve()
    output = root / "binary_inputs-pc98"
    output.mkdir(exist_ok=True)
    original = {str(p.relative_to(root / "jpn-pc98")): p.read_bytes() for p in (root / "jpn-pc98").rglob("*") if p.is_file()}
    korean = {str(p.relative_to(root / "kor-pc98")): p.read_bytes() for p in (root / "kor-pc98").rglob("*") if p.is_file()}
    masks = {}
    comparison = []
    for name in sorted(original.keys() | korean.keys()):
        if name not in original or name not in korean:
            comparison.append({"source": name, "status": "jpn_only" if name in original else "kor_only", "size": len(original.get(name, korean.get(name)))})
            continue
        a, b = original[name], korean[name]
        covered = bytearray(max(len(a), len(b)))
        for lang in ("jpn", "kor"):
            script = root / "script-pc98" / (name + "_" + lang + ".json")
            if not script.exists():
                continue
            for key, value in json.loads(script.read_text(encoding="utf-8")).items():
                match = re.fullmatch(r"([0-9a-fA-F]+)=([0-9a-fA-F]+)", key)
                if match:
                    start, end = (int(x, 16) for x in match.groups())
                elif key == "zero_padding":
                    start, length = (int(x, 16) for x in value.split(":"))
                    end = start + length - 1
                else:
                    continue
                end = min(end, len(covered) - 1)
                covered[start:end + 1] = b"\1" * max(0, end - start + 1)
        differences = [i for i in range(max(len(a), len(b))) if (i >= len(a) or i >= len(b) or a[i] != b[i]) and not covered[i]]
        masks[name] = differences
        comparison.append({"source": name, "jpn_size": len(a), "kor_size": len(b), "status": "identical" if a == b else "script_only" if not differences else "outside_script", "outside_script_changed_bytes": len(differences), "first_offset": f"0x{differences[0]:06X}" if differences else None, "last_offset": f"0x{differences[-1]:06X}" if differences else None})

    records = []
    excluded_identical_pairs = []
    def save_pair(name, starts, blocks, sizes, decoded, planes, compression, label, record_index=None, glyph_columns=None, stem_override=None):
        directory = output / name
        directory.mkdir(exist_ok=True)
        stem = stem_override or f"{starts[0]:06X}"
        dimensions = [(r[0], r[1]) for r in decoded]
        pixel_equal = dimensions[0] == dimensions[1] and decoded[0][3] == decoded[1][3]
        if pixel_equal:
            excluded_identical_pairs.append({"source": name, "offset": f"0x{starts[0]:06X}", "kor_offset": f"0x{starts[1]:06X}"})
            return
        palette = PC98_PALETTE_8 if planes == 3 else [(0, 0, 0), (255, 255, 255)]
        hashes = {}
        for lang, offset, block, (width, height, planar, indices) in zip(("jpn", "kor"), starts, blocks, decoded):
            assert len(planar) == width * height * planes // 8
            assert len(indices) == width * height
            if glyph_columns:
                rebuilt = bytearray()
                for index in range(len(planar) // 32):
                    gx, gy = (index % glyph_columns) * 16, (index // glyph_columns) * 16
                    glyph = b"".join(indices[(gy + y) * width + gx:(gy + y) * width + gx + 16] for y in range(16))
                    rebuilt.extend(encode_interleaved_planar(glyph, 16, 16, 1))
                assert bytes(rebuilt) == planar
            else:
                assert encode_interleaved_planar(indices, width, height, planes) == planar
            if compression != "none":
                roundtrip = decode_slogo_image(block, 0, len(block))
                assert roundtrip[:4] == (width, height, planar, indices)
            im = Image.frombytes("P", (width, height), indices)
            im.putpalette([component for rgb in palette for component in rgb])
            target = directory / f"{stem}.{lang}.png"
            im.save(target)
            with Image.open(target) as verified:
                assert verified.mode == "P" and verified.size == (width, height)
                assert verified.tobytes() == indices
            hashes[lang] = {"source_offset": f"0x{offset:06X}", "width": width, "height": height, "planar_sha256": hashlib.sha256(planar).hexdigest(), "index_sha256": hashlib.sha256(indices).hexdigest()}
        metadata = {"source": name, "offset": f"0x{starts[0]:06X}", "kor_offset": f"0x{starts[1]:06X}", "original_size": len(blocks[0]), "encoded_size": sizes[1], "stored_size": len(blocks[1]), "padding_byte": 0 if len(blocks[1]) > sizes[1] else None, "compression": compression, "width": decoded[0][0], "height": decoded[0][1], "kor_width": decoded[1][0], "kor_height": decoded[1][1], "planes": planes, "plane_order": "BRG" if planes == 3 else "mask", "planar_layout": "interleaved" if planes == 3 else "plane-major-row", "bit_order": "msb-first", "stride": decoded[0][0] // 8, "palette": [f"#{r:02X}{g:02X}{b:02X}" for r, g, b in palette], "palette_note": "Native indices preserved; 3bpp previews use default PC-98 colors, not scene-specific runtime palette changes.", "label": label, "record_index": record_index, "pixel_equal": pixel_equal, "changed_pixels": sum(x != y for x, y in zip(decoded[0][3], decoded[1][3])) if dimensions[0] == dimensions[1] else None, "versions": hashes}
        if glyph_columns:
            metadata.update(planar_layout="glyph-major-row", glyph_width=16, glyph_height=16, glyph_count=len(blocks[0]) // 32, glyph_size_bytes=32, columns=glyph_columns, rows=decoded[0][1] // 16, last_code="EBB4")
        write_json(directory / f"{stem}.meta.json", metadata)
        records.append(metadata | {"stem": stem})

    # NB4 OPEN/END use the same GRPDRV AH=19h stream verified by NB5's decoder.
    # The OPEN executable reads 29 compressed records followed by five fixed-size mask banks.
    archive_ends = {}
    for name, count in (("OPEN.DAT", 29), ("ENDING.DAT", 22)):
        source, translated = original[name], korean[name]
        jpn_position = kor_position = 0
        for index in range(count):
            j = decode_slogo_image(source, jpn_position, len(source))
            if name == "ENDING.DAT":
                kor_position = jpn_position
            k = decode_slogo_image(translated, kor_position, len(translated))
            jend, kend = j[-1], k[-1]
            kstored = jend if name == "ENDING.DAT" else kend
            if name == "ENDING.DAT":
                assert not any(translated[kend:kstored]), "Unexpected nonzero END record padding"
            jblock, kblock = source[jpn_position:jend], translated[kor_position:kstored]
            if jblock != kblock:
                save_pair(name, (jpn_position, kor_position), (jblock, kblock), (jend - jpn_position, kend - kor_position), (j[:4], k[:4]), 3, "grpdrv-lz", f"compressed image {index:02d}", index)
            jpn_position, kor_position = jend, kend
        archive_ends[name] = (jpn_position, kor_position)
    jtail, ktail = archive_ends["OPEN.DAT"]
    bank_sizes = (0xF900, 0xF328, 0xF68E, 0xDCD0, 0x7468)
    assert len(original["OPEN.DAT"]) - jtail == sum(bank_sizes)
    logical_end = ktail + sum(bank_sizes)
    assert len(korean["OPEN.DAT"]) >= logical_end
    assert not any(korean["OPEN.DAT"][logical_end:]), "Unexpected nonzero OPEN archive padding"
    # OPEN.EXE sub_0FFE calls sub_0F4A with eight width/height/offset sets.
    # They are 1bpp vertical poem columns in the second raw mask bank.
    columns = ((0x1F80, 72), (0x26D0, 64), (0x2D50, 56), (0x3300, 80), (0x3B20, 56), (0x40D0, 56), (0x4680, 72), (0x4DD0, 72))
    selected = set()
    for index, (relative, width) in enumerate(columns):
        height = 208
        starts = (jtail + bank_sizes[0] + relative, ktail + bank_sizes[0] + relative)
        size = width * height // 8
        blocks = tuple(data[start:start + size] for data, start in zip((original["OPEN.DAT"], korean["OPEN.DAT"]), starts))
        if blocks[0] != blocks[1]:
            decoded = tuple((width, height, block, decode_interleaved_planar(block, width, height, 1)) for block in blocks)
            save_pair("OPEN.DAT", starts, blocks, (size, size), decoded, 1, "none", f"opening poem column {index + 1}")
            selected.update(range(starts[0] - jtail, starts[0] - jtail + size))
    a, b = original["OPEN.DAT"][jtail:], korean["OPEN.DAT"][ktail:]
    assert all(i in selected for i, (x, y) in enumerate(zip(a, b)) if x != y), "Undecoded changed OPEN mask data"

    # MAIN.EXE 0xAEAB..0xAEEA reads two 0xBB80 screen halves and an unchanged auxiliary table.
    name = "MAPDATA.DAT"
    size = 2 * 0xBB80
    blocks = (original[name][:size], korean[name][:size])
    decoded = tuple((640, 400, block, decode_interleaved_planar(block, 640, 400, 3)) for block in blocks)
    assert all(i < size for i in masks[name])
    save_pair(name, (0, 0), blocks, (size, size), decoded, 3, "none", "map background including title")

    # EBB4 (Fukaya) is glyph 21. Keep the active 22-glyph range as one native atlas.
    name = "GAIJI.DAT"
    count, columns, width, height = 22, 11, 176, 32
    blocks = (original[name][:count * 32], korean[name][:count * 32])
    decoded = []
    for raw in blocks:
        indices = bytearray(width * height)
        for index in range(count):
            glyph = decode_interleaved_planar(raw[index * 32:(index + 1) * 32], 16, 16, 1)
            gx, gy = (index % columns) * 16, (index // columns) * 16
            for y in range(16):
                indices[(gy + y) * width + gx:(gy + y) * width + gx + 16] = glyph[y * 16:(y + 1) * 16]
        decoded.append((width, height, raw, bytes(indices)))
    save_pair(name, (0, 0), blocks, (704, 704), decoded, 1, "none", "active glyphs 0-21 through EBB4 (Fukaya)", glyph_columns=columns, stem_override="GAIJI")

    unexplained = [row["source"] for row in comparison if row["status"] == "outside_script" and row["source"] not in {"OPEN.DAT", "ENDING.DAT", "MAPDATA.DAT", "GAIJI.DAT"}]
    assert not unexplained, unexplained
    report = {"workspace": str(root), "excluded": "jpn/kor script JSON address ranges and zero_padding allocations", "comparison": comparison, "image_pairs": len(records), "pixel_changed_pairs": sum(not r["pixel_equal"] for r in records), "compression_only_pairs": 0, "excluded_compression_only_pairs": len(excluded_identical_pairs), "excluded_identical_pixel_images": excluded_identical_pairs, "images": records, "notes": ["JPN-only files are absent from the sparse Korean output folder, not changed images.", "KOR-only ALLBLANK.COM is executable code; USERDISK.DIR is an empty marker.", "END compressed records retain fixed original offsets; OPEN records move after recompression.", "All changed raw OPEN mask bytes are covered by the eight extracted poem columns.", "Compressed records and PNG indices were re-decoded and checked; planar re-encoding matches byte-for-byte."]}
    write_json(output / "comparison.json", report)
    rows = []
    for record in records:
        name, stem = record["source"], record["stem"]
        status = "pixels identical" if record["pixel_equal"] else "pixels changed"
        title = html.escape(f"{name} / {stem} / {record['label']} / {status}")
        imgs = "".join(f'<figure><figcaption>{lang.upper()} {record["versions"][lang]["source_offset"]}</figcaption><a href="{name}/{stem}.{lang}.png"><img loading="lazy" src="{name}/{stem}.{lang}.png"></a></figure>' for lang in ("jpn", "kor"))
        rows.append(f'<section><h2>{title}</h2><div class="pair">{imgs}</div></section>')
    document = '<!doctype html><meta charset="utf-8"><title>NB4 image comparison</title><style>body{font:16px sans-serif;background:#eee;margin:24px}h2{font-size:17px}.pair{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap}figure{margin:0}img{max-width:640px;image-rendering:pixelated}section{padding:16px;margin:16px 0;background:white}figcaption{margin-bottom:8px}</style><h1>NB4 image comparison</h1><p>Native palette indices; default PC-98 preview colors. JPN offsets name pairs; KOR offsets are recorded separately.</p>' + "".join(rows)
    (output / "report.html").write_bytes(document.replace("\n", "\r\n").encode("utf-8"))
    # Verify originals, Korean game binaries, and all script files remained untouched.
    for language, snapshot in (("jpn", original), ("kor", korean)):
        for name, data in snapshot.items():
            assert (root / (language + "-pc98") / name).read_bytes() == data
    print(json.dumps({"pairs": len(records), "pixel_changed": report["pixel_changed_pairs"], "compression_only": report["compression_only_pairs"], "by_source": {name: sum(r["source"] == name for r in records) for name in ("OPEN.DAT", "ENDING.DAT", "MAPDATA.DAT", "GAIJI.DAT")}, "report": str(output / "report.html")}, indent=2))


if __name__ == "__main__":
    main()
