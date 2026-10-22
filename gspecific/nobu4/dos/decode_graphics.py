"""Decode Japanese DOS images corresponding to the retained NB4 translation assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("C:/work_han/workspace0"))
    parser.add_argument("--code-root", type=Path, default=Path("C:/work_han/translation"))
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_root))
    from PIL import Image
    from gspecific.nobu5.decode_graphics import decode_slogo_image
    from module.pc98_image.planar import decode_interleaved_planar, encode_interleaved_planar

    root = args.workspace.resolve()
    output = root / "binary_inputs-dos"
    source = {name: (root / "jpn-dos" / name).read_bytes() for name in ("OPEN.DAT", "ENDING.DAT", "MAPDATA.DAT", "GAIJI.DAT")}
    selection = [
        {"source": "OPEN.DAT", "compression": "grpdrv-lz", "record_index": n, "label": f"compressed image {n:02d}"}
        for n in (*range(2, 10), *range(14, 29))
    ]
    selection += [{"source": "OPEN.DAT", "compression": "none", "label": f"poem column {n}"} for n in range(1, 9)]
    selection += [
        {"source": "ENDING.DAT", "compression": "grpdrv-lz", "record_index": 19, "label": "ending image 19"},
        {"source": "MAPDATA.DAT", "compression": "none", "label": "map title"},
        {"source": "GAIJI.DAT", "compression": "none", "label": "glyph atlas through Fukaya"},
    ]
    palette = [(0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]
    archives = {}
    for name, count in (("OPEN.DAT", 29), ("ENDING.DAT", 22)):
        records = []
        position = 0
        for index in range(count):
            decoded = decode_slogo_image(source[name], position, len(source[name]))
            records.append((position, decoded))
            position = decoded[-1]
        archives[name] = records
    tail = archives["OPEN.DAT"][-1][1][-1]
    assert len(source["OPEN.DAT"]) - tail == sum((0xF900, 0xF328, 0xF68E, 0xDCD0, 0x7468))
    poem_columns = ((0x1F80, 72), (0x26D0, 64), (0x2D50, 56), (0x3300, 80), (0x3B20, 56), (0x40D0, 56), (0x4680, 72), (0x4DD0, 72))
    results = []
    for selected in selection:
        name = selected["source"]
        label = selected["label"]
        glyph_columns = None
        if selected["compression"] == "grpdrv-lz":
            offset, decoded = archives[name][selected["record_index"]]
            width, height, planar, indices, end = decoded
            original_size = end - offset
            assert decode_slogo_image(source[name][offset:end], 0, original_size)[:4] == decoded[:4]
            planes, layout, compression = 3, "interleaved", "grpdrv-lz"
            stem = f"{offset:06X}"
        elif name == "OPEN.DAT":
            column = int(label.rsplit(" ", 1)[-1]) - 1
            relative, width = poem_columns[column]
            height, planes = 208, 1
            offset = tail + 0xF900 + relative
            original_size = width * height // 8
            planar = source[name][offset:offset + original_size]
            indices = decode_interleaved_planar(planar, width, height, planes)
            layout, compression, stem = "plane-major-row", "none", f"{offset:06X}"
        elif name == "MAPDATA.DAT":
            width, height, planes, offset, original_size = 640, 400, 3, 0, 96000
            planar = source[name][:original_size]
            indices = decode_interleaved_planar(planar, width, height, planes)
            layout, compression, stem = "interleaved", "none", "000000"
        elif name == "GAIJI.DAT":
            width, height, planes, offset, original_size = 176, 32, 1, 0, 704
            planar = source[name][:original_size]
            glyph_columns = 11
            indices = bytearray(width * height)
            for index in range(22):
                glyph = decode_interleaved_planar(planar[index * 32:(index + 1) * 32], 16, 16, 1)
                gx, gy = index % glyph_columns * 16, index // glyph_columns * 16
                for y in range(16):
                    indices[(gy + y) * width + gx:(gy + y) * width + gx + 16] = glyph[y * 16:(y + 1) * 16]
            indices = bytes(indices)
            layout, compression, stem = "glyph-major-row", "none", "GAIJI"
        else:
            raise ValueError(f"Unsupported selection: {name}")
        if glyph_columns:
            rebuilt = bytearray()
            for index in range(22):
                gx, gy = index % glyph_columns * 16, index // glyph_columns * 16
                glyph = b"".join(indices[(gy + y) * width + gx:(gy + y) * width + gx + 16] for y in range(16))
                rebuilt.extend(encode_interleaved_planar(glyph, 16, 16, 1))
            assert bytes(rebuilt) == planar
        else:
            assert encode_interleaved_planar(indices, width, height, planes) == planar
        colors = palette if planes == 3 else [(0, 0, 0), (255, 255, 255)]
        directory = output / name
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{stem}.jpn.png"
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite an existing PNG: {target}")
        image = Image.frombytes("P", (width, height), indices)
        image.putpalette([value for color in colors for value in color])
        image.save(target)
        with Image.open(target) as verified:
            assert verified.size == (width, height) and verified.tobytes() == indices
        metadata = {"platform": "dos", "source": name, "offset": f"0x{offset:06X}", "original_size": original_size, "encoded_size": None, "stored_size": None, "padding_byte": None, "compression": compression, "width": width, "height": height, "planes": planes, "plane_order": "BRG" if planes == 3 else "mask", "planar_layout": layout, "bit_order": "msb-first", "stride": width // 8 if not glyph_columns else None, "palette": [f"#{r:02X}{g:02X}{b:02X}" for r, g, b in colors], "palette_note": "Native indices with default 8-color B/R/G preview palette; scene-specific palette changes are not applied.", "label": label, "record_index": selected.get("record_index"), "source_sha256": hashlib.sha256(source[name]).hexdigest(), "index_sha256": hashlib.sha256(indices).hexdigest()}
        if glyph_columns:
            metadata.update(glyph_width=16, glyph_height=16, glyph_count=22, glyph_size_bytes=32, columns=11, rows=2, last_code="EBB4")
        (directory / f"{stem}.meta.json").write_bytes((json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8"))
        results.append({"source": name, "png": str(target.relative_to(output)).replace("\\", "/"), "width": width, "height": height, "offset": metadata["offset"]})
    for name, data in source.items():
        assert (root / "jpn-dos" / name).read_bytes() == data
    assert len(results) == 34 and len(list(output.rglob("*.png"))) == 34
    assert not list(output.rglob("*.bin")) and not list(output.rglob("*.kor.png"))
    summary = {"platform": "dos", "source_root": "jpn-dos", "png_count": len(results), "by_source": {name: sum(row["source"] == name for row in results) for name in source}, "images": results}
    (output / "decoding_report.json").write_bytes((json.dumps(summary, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8"))
    print(json.dumps({"png_count": len(results), "by_source": summary["by_source"], "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
