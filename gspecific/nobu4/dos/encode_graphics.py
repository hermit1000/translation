#!/usr/bin/env python3
"""Encode NB4 DOS Korean sub-images to final per-image binaries only."""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

from PIL import Image

# Works both in translation/gspecific/nobu4 and as a staged standalone file.
code_root = Path(__file__).resolve().parents[3]
if not (code_root / 'module').is_dir():
    code_root = Path('C:/work_han/translation')
sys.path.insert(0, str(code_root))
from gspecific.nobu5.decode_graphics import decode_slogo_image
from module.pc98_image.planar import encode_interleaved_planar, decode_interleaved_planar


def encode_grpdrv(indices: bytes, width: int, height: int) -> bytes:
    """Encode native DOS 3bpp row-bounded literal/RLE/LZ commands."""
    if width % 8 or len(indices) != width * height or any(p > 7 for p in indices):
        raise ValueError('Invalid 3bpp geometry or palette indices')
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
    output = bytearray(struct.pack('<HH', width, height))
    for y, row in enumerate(rows):
        n = len(row)
        cost, choices = [0] * (n + 1), [None] * n
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


def encode_glyph_atlas(indices, width, height, meta):
    count, columns = meta['glyph_count'], meta['columns']
    if width != columns * 16 or height != ((count + columns - 1) // columns) * 16:
        raise ValueError('Gaiji atlas geometry differs from its glyph layout')
    output, restored = bytearray(), bytearray(width * height)
    for index in range(count):
        gx, gy = index % columns * 16, index // columns * 16
        glyph = b''.join(indices[(gy + y) * width + gx:(gy + y) * width + gx + 16] for y in range(16))
        block = encode_interleaved_planar(glyph, 16, 16, 1)
        output.extend(block)
        decoded = decode_interleaved_planar(block, 16, 16, 1)
        for y in range(16):
            restored[(gy + y) * width + gx:(gy + y) * width + gx + 16] = decoded[y * 16:(y + 1) * 16]
    if bytes(restored) != indices:
        raise ValueError('Gaiji atlas round-trip mismatch')
    return bytes(output)


def encode_all(workspace: Path, source: str | None = None) -> list[Path]:
    inputs = workspace / 'binary_inputs-dos'
    if not inputs.is_dir():
        raise FileNotFoundError(inputs)
    jobs = []
    for path in sorted(inputs.rglob('*.meta.json')):
        meta = json.loads(path.read_text(encoding='utf-8'))
        if source is not None and meta['source'].upper() != source.upper():
            continue
        if meta.get('platform') != 'dos':
            raise ValueError(f'Not DOS metadata: {path}')
        stem = path.name.removesuffix('.meta.json')
        png = path.parent / (stem + '.kor.png')
        width, height = meta.get('kor_width', meta['width']), meta.get('kor_height', meta['height'])
        palette = {tuple(bytes.fromhex(c.removeprefix('#'))): i for i, c in enumerate(meta['palette'])}
        with Image.open(png) as image:
            if image.size != (width, height):
                raise ValueError(f'PNG size differs from metadata: {png}')
            try:
                indices = bytes(palette[c] for c in image.convert('RGB').getdata())
            except KeyError as error:
                raise ValueError(f'PNG contains a color outside its native palette: {png}') from error
        if meta['compression'] == 'grpdrv-lz':
            data = encode_grpdrv(indices, width, height)
            decoded = decode_slogo_image(data, 0, len(data))
            if decoded[:2] != (width, height) or decoded[3] != indices or decoded[-1] != len(data):
                raise ValueError(f'Compressed round-trip mismatch: {png}')
            if meta['source'] == 'ENDING.DAT':
                capacity = meta['original_size']
                if len(data) > capacity:
                    raise ValueError(f'Ending image exceeds fixed slot: {png} ({len(data)} > {capacity})')
                data += bytes(capacity - len(data))
            target = path.parent / (stem + '.cmp.kor.bin')
        elif meta['compression'] == 'none':
            if meta['planar_layout'] == 'glyph-major-row':
                data = encode_glyph_atlas(indices, width, height, meta)
            else:
                data = encode_interleaved_planar(indices, width, height, meta['planes'])
                if decode_interleaved_planar(data, width, height, meta['planes']) != indices:
                    raise ValueError(f'Planar round-trip mismatch: {png}')
            if len(data) != meta['original_size']:
                raise ValueError(f'Raw image size differs from its original slot: {png}')
            target = path.parent / (stem + '.pln.kor.bin')
        else:
            raise ValueError(f'Unsupported compression: {path}')
        jobs.append((target, data))
    if not jobs:
        raise ValueError('No matching Korean sub-images found')
    # Publish only after all selected images pass palette, size and round-trip checks.
    for target, data in jobs:
        target.write_bytes(data)
        if target.read_bytes() != data:
            raise OSError(f'Binary write verification failed: {target}')
        print(f'{target.relative_to(workspace)}: {len(data)} bytes')
    return [target for target, _ in jobs]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path('C:/work_han/workspace0'))
    parser.add_argument('--source', help='Encode only one source file, e.g. OPEN.DAT')
    args = parser.parse_args()
    paths = encode_all(args.workspace.resolve(), args.source)
    print(f'Encoded {len(paths)} final DOS sub-image binaries.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
