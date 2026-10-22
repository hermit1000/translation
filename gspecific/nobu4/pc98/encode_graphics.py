"""Encode retained NB4 Korean PNGs to final insertion blocks only."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


def encode_grpdrv(indices: bytes, width: int, height: int) -> bytes:
    """Encode the 3bpp GRPDRV AH=19h stream using row-bounded RLE/LZ."""
    if width % 8 or len(indices) != width * height or any(p > 7 for p in indices):
        raise ValueError("Invalid 3bpp dimensions or indices")
    rows = []
    for y in range(height):
        row = []
        for x in range(0, width, 4):
            pattern = 0
            for bit in range(4):
                color = indices[y * width + x + bit]
                for plane in range(3):
                    if color & (1 << plane):
                        pattern |= (8 >> bit) << (4 * plane)
            row.append(pattern)
        rows.append(row)
    output = bytearray(struct.pack("<HH", width, height))
    for y, row in enumerate(rows):
        n = len(row)
        cost = [0] * (n + 1)
        choices = [None] * n
        for x in range(n - 1, -1, -1):
            best = (2 + cost[x + 1], 1, None)
            repeat = 1
            while repeat < min(8, n - x) and row[x + repeat] == row[x]:
                repeat += 1
            for length in range(1, repeat + 1):
                if 2 + cost[x + length] < best[0]:
                    best = (2 + cost[x + length], length, None)
            for vertical in (False, True):
                for distance in range(1, 5):
                    if (vertical and y < distance) or (not vertical and x < distance):
                        continue
                    reference = rows[y - distance] if vertical else row
                    start = x if vertical else x - distance
                    length = 0
                    while length < min(16, n - x) and row[x + length] == reference[start + length]:
                        length += 1
                    command = 0x80 | (0x40 if vertical else 0) | ((distance - 1) << 4)
                    for count in range(1, length + 1):
                        if 1 + cost[x + count] < best[0]:
                            best = (1 + cost[x + count], count, command)
            cost[x], count, command = best
            choices[x] = (count, command)
        x = 0
        while x < n:
            count, command = choices[x]
            if command is None:
                output.extend((((count - 1) << 4) | (row[x] >> 8), row[x] & 255))
            else:
                output.append(command | (count - 1))
            x += count
    return bytes(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("C:/work_han/workspace0"))
    parser.add_argument("--code-root", type=Path, default=Path("C:/work_han/translation"))
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_root))
    from PIL import Image
    from module.pc98_image.planar import encode_interleaved_planar, decode_interleaved_planar
    from gspecific.nobu5.decode_graphics import decode_slogo_image

    root = args.workspace.resolve()
    input_root = root / "binary_inputs-pc98"
    png_hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in input_root.rglob("*.png")}
    references = {name: (root / "kor-pc98" / name).read_bytes() for name in ("OPEN.DAT", "ENDING.DAT", "MAPDATA.DAT", "GAIJI.DAT")}
    jobs = []
    for meta_path in sorted(input_root.rglob("*.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        stem = meta_path.name.removesuffix(".meta.json")
        png_path = meta_path.parent / f"{stem}.kor.png"
        width, height = meta.get("kor_width", meta["width"]), meta.get("kor_height", meta["height"])
        planes = meta["planes"]
        palette = [tuple(bytes.fromhex(color.removeprefix("#"))) for color in meta["palette"]]
        lookup = {color: index for index, color in enumerate(palette)}
        with Image.open(png_path) as image:
            if image.size != (width, height):
                raise ValueError(f"{png_path}: size differs from metadata")
            try:
                indices = bytes(lookup[color] for color in image.convert("RGB").getdata())
            except KeyError as error:
                raise ValueError(f"{png_path}: color {error.args[0]} is outside the game palette") from error

        offset = int(meta["kor_offset"], 16)
        encoding_mode = "encoded_from_png"
        if meta["compression"] == "grpdrv-lz":
            encoded = encode_grpdrv(indices, width, height)
            decoded = decode_slogo_image(encoded, 0, len(encoded))
            assert decoded[0:2] == (width, height) and decoded[3] == indices
            assert decoded[-1] == len(encoded)
            # Preserve an equivalent existing compressed representation to avoid
            # relocating OPEN records or changing the OPEN.EXE resource tables.
            reference = references[meta["source"]][offset:offset + meta["stored_size"]]
            reference_decoded = decode_slogo_image(reference, 0, len(reference))
            if reference_decoded[0:2] == (width, height) and reference_decoded[3] == indices:
                encoded = reference[:reference_decoded[-1]]
                encoding_mode = "verified_equivalent_reference"
            stored = encoded
            if meta["source"] == "ENDING.DAT":
                capacity = meta["original_size"]
                if len(encoded) > capacity:
                    raise ValueError(f"{png_path}: compressed size {len(encoded)} exceeds fixed slot {capacity}")
                stored += bytes(capacity - len(encoded))
            target = meta_path.parent / f"{stem}.cmp.kor.bin"
            assert decode_slogo_image(stored, 0, len(stored))[3] == indices
            needs_repack = meta["source"] == "OPEN.DAT" and len(stored) != meta["stored_size"]
        elif meta["planar_layout"] == "glyph-major-row":
            encoded = bytearray()
            count, columns = meta["glyph_count"], meta["columns"]
            rebuilt = bytearray(width * height)
            for index in range(count):
                gx, gy = index % columns * 16, index // columns * 16
                glyph = b"".join(indices[(gy + y) * width + gx:(gy + y) * width + gx + 16] for y in range(16))
                encoded.extend(encode_interleaved_planar(glyph, 16, 16, 1))
                decoded_glyph = decode_interleaved_planar(encoded[-32:], 16, 16, 1)
                for y in range(16):
                    rebuilt[(gy + y) * width + gx:(gy + y) * width + gx + 16] = decoded_glyph[y * 16:(y + 1) * 16]
            assert bytes(rebuilt) == indices and len(encoded) == count * 32
            encoded = stored = bytes(encoded)
            target = meta_path.parent / f"{stem}.pln.kor.bin"
            needs_repack = False
        elif meta["compression"] == "none":
            encoded = stored = encode_interleaved_planar(indices, width, height, planes)
            assert decode_interleaved_planar(stored, width, height, planes) == indices
            assert len(stored) == meta["original_size"]
            target = meta_path.parent / f"{stem}.pln.kor.bin"
            needs_repack = False
        else:
            raise ValueError(f"Unsupported format: {meta_path}")
        matches_reference = stored == references[meta["source"]][offset:offset + len(stored)]
        jobs.append((target, stored, meta_path, meta, {"source": meta["source"], "stem": stem, "binary": str(target.relative_to(input_root)).replace("\\", "/"), "kor_offset": meta["kor_offset"], "encoded_size": len(encoded), "stored_size": len(stored), "padding_byte": 0 if len(stored) > len(encoded) else None, "encoding_mode": encoding_mode, "requires_open_repack": needs_repack, "matches_current_kor_binary": matches_reference, "binary_sha256": hashlib.sha256(stored).hexdigest(), "png_sha256": png_hashes[png_path]}))

    # Do not publish partial results if any encoding/size check fails.
    for target, stored, meta_path, meta, result in jobs:
        target.write_bytes(stored)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == result["binary_sha256"]
        meta.update({key: result[key] for key in ("encoded_size", "stored_size", "padding_byte", "encoding_mode", "requires_open_repack", "binary_sha256")})
        meta["final_binary"] = target.name
        meta_path.write_bytes((json.dumps(meta, ensure_ascii=False, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8"))
    for p, digest in png_hashes.items():
        assert hashlib.sha256(p.read_bytes()).hexdigest() == digest
    for name, reference in references.items():
        assert (root / "kor-pc98" / name).read_bytes() == reference
    assert {p.resolve() for p in input_root.rglob("*.bin")} == {job[0].resolve() for job in jobs}
    results = [job[-1] for job in jobs]
    log = {"final_binaries": len(results), "png_files_preserved": len(png_hashes), "requires_open_repack": any(r["requires_open_repack"] for r in results), "results": results}
    (input_root / "encoding_report.json").write_bytes((json.dumps(log, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8"))
    print(json.dumps({"final_binaries": len(results), "compressed": sum(job[0].name.endswith(".cmp.kor.bin") for job in jobs), "raw_planar": sum(job[0].name.endswith(".pln.kor.bin") for job in jobs), "all_match_current_kor": all(r["matches_current_kor_binary"] for r in results), "requires_open_repack": log["requires_open_repack"], "png_files_preserved": len(png_hashes)}, indent=2))


if __name__ == "__main__":
    main()
