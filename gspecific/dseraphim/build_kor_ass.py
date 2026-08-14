#!/usr/bin/env python3
"""Build Korean OPEN/END ASS files from the translated JSON documents."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from extract_ass import (
    DECOMPRESSED_ADDRESS_BASE,
    SPECS,
    AssSpec,
    DecodeError,
    decompress_ass,
    load_font_table,
)


@dataclass(frozen=True)
class BuildSpec:
    ass: AssSpec
    translation_name: str
    output_name: str


BUILD_SPECS = (
    BuildSpec(
        ass=SPECS[0],
        translation_name="OPEN_decoded.ASS_kor.json",
        output_name="OPEN_kor.ASS",
    ),
    BuildSpec(
        ass=SPECS[1],
        translation_name="END_decoded.ASS_kor.json",
        output_name="END_kor.ASS",
    ),
)

# The Korean JSON uses U+00B7, while the font table names the same middle-dot
# glyph with U+30FB.
CHARACTER_ALIASES = {"·": "・"}
MAX_LOADER_READ_SIZE = 0x1770


def reverse_font_table(font_table: dict[str, str]) -> dict[str, list[str]]:
    reverse: dict[str, list[str]] = defaultdict(list)
    for code, character in font_table.items():
        reverse[character].append(code)
    return dict(reverse)


def load_translation(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8") as translation_file:
        document = json.load(translation_file)
    if not isinstance(document, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in document.items()
    ):
        raise DecodeError(f"{path}: translation must be a JSON string map")
    return document


def text_spans(encoded: bytes, start_address: int) -> list[str]:
    spans: list[str] = []
    segment_start = 0
    for cursor in range(len(encoded) + 1):
        at_end = cursor == len(encoded)
        if not at_end and encoded[cursor] != 0:
            continue
        if cursor > segment_start:
            first = start_address + segment_start
            last = start_address + cursor - 1
            spans.append(f"{first:05X}={last:05X}")
        segment_start = cursor + 1
    return spans


def encode_translation(
    text: str,
    original: bytes,
    reverse_table: dict[str, list[str]],
    span: str,
) -> bytes:
    if len(text) * 2 != len(original):
        raise DecodeError(
            f"{span}: {len(text)} characters require {len(text) * 2} bytes, "
            f"but the assigned range is {len(original)} bytes"
        )

    encoded = bytearray()
    for index, source_character in enumerate(text):
        character = CHARACTER_ALIASES.get(source_character, source_character)
        candidates = reverse_table.get(character)
        if not candidates:
            raise DecodeError(
                f"{span}: character {source_character!r} is missing from "
                "the Korean font table"
            )

        original_code = original[index * 2 : index * 2 + 2].hex().upper()
        code = original_code if original_code in candidates else candidates[0]
        encoded.extend(bytes.fromhex(code))
    return bytes(encoded)


def decompress_rle(encoded: bytes) -> tuple[bytes, dict[int, int]]:
    """Decode the second ASS stage and map literal source bytes to output."""
    if len(encoded) < 4:
        raise DecodeError("RLE stream is shorter than its four-byte header")

    marker = encoded[0]
    expected_size = int.from_bytes(encoded[2:4], "little")
    output = bytearray()
    literal_map: dict[int, int] = {}
    cursor = 4

    while len(output) < expected_size:
        if cursor >= len(encoded):
            raise DecodeError(
                f"RLE stream ended after {len(output)} of "
                f"{expected_size} decoded bytes"
            )

        source_offset = cursor
        value = encoded[cursor]
        cursor += 1
        if value != marker:
            literal_map[source_offset] = len(output)
            output.append(value)
            continue

        if cursor + 2 > len(encoded):
            raise DecodeError(
                f"truncated RLE token at source offset 0x{source_offset:X}"
            )
        repeated_value = encoded[cursor]
        count = encoded[cursor + 1] or 0x100
        cursor += 2
        if len(output) + count > expected_size:
            raise DecodeError(
                f"RLE token at source offset 0x{source_offset:X} exceeds "
                f"the declared output size {expected_size}"
            )
        output.extend([repeated_value] * count)

    if cursor != len(encoded):
        raise DecodeError(
            f"RLE stream has {len(encoded) - cursor} trailing compressed bytes"
        )
    return bytes(output), literal_map


def compress_rle(decoded: bytes, template: bytes) -> bytes:
    """Encode the second ASS stage using literal bytes and run tokens."""
    if len(template) < 4:
        raise DecodeError("RLE template is shorter than its four-byte header")
    if len(decoded) > 0xFFFF:
        raise DecodeError("RLE output is too large for its 16-bit header")

    marker = template[0]
    output = bytearray(template[:2])
    output.extend(len(decoded).to_bytes(2, "little"))
    cursor = 0

    while cursor < len(decoded):
        value = decoded[cursor]
        run_length = 1
        while (
            cursor + run_length < len(decoded)
            and decoded[cursor + run_length] == value
        ):
            run_length += 1

        remaining = run_length
        while remaining:
            chunk = min(remaining, 0x100)
            if value == marker or chunk >= 4:
                output.extend((marker, value, 0 if chunk == 0x100 else chunk))
                cursor += chunk
                remaining -= chunk
                continue

            output.extend([value] * chunk)
            cursor += chunk
            remaining -= chunk

    return bytes(output)


def patch_translations(
    rle_stream: bytes,
    final_image: bytes,
    literal_map: dict[int, int],
    spec: AssSpec,
    translations: dict[str, str],
    reverse_table: dict[str, list[str]],
) -> bytes:
    patched = bytearray(final_image)
    range_start = spec.text_start - DECOMPRESSED_ADDRESS_BASE
    range_end = spec.text_end - DECOMPRESSED_ADDRESS_BASE + 1
    original_text = rle_stream[range_start:range_end]

    expected_spans = text_spans(original_text, spec.text_start)
    if list(translations) != expected_spans:
        raise DecodeError(
            f"{spec.source_name}: translation address keys do not exactly "
            "match the original text spans"
        )

    for span, text in translations.items():
        first, last = (int(value, 16) for value in span.split("="))
        source_start = first - DECOMPRESSED_ADDRESS_BASE
        source_end = last - DECOMPRESSED_ADDRESS_BASE + 1
        try:
            output_offsets = [
                literal_map[offset] for offset in range(source_start, source_end)
            ]
        except KeyError as error:
            raise DecodeError(
                f"{span}: original text intersects an RLE control token"
            ) from error

        output_start = output_offsets[0]
        output_end = output_offsets[-1] + 1
        if output_offsets != list(range(output_start, output_end)):
            raise DecodeError(f"{span}: text bytes are not contiguous after RLE")

        patched[output_start:output_end] = encode_translation(
            text,
            original=final_image[output_start:output_end],
            reverse_table=reverse_table,
            span=span,
        )
    return bytes(patched)


def compress_body(decoded: bytes, marker: int) -> bytes:
    """Greedy encoder for the 12-bit-distance/4-bit-length ASS LZ format."""
    output = bytearray()
    positions: dict[bytes, list[int]] = defaultdict(list)
    cursor = 0

    def remember(position: int) -> None:
        if position + 4 <= len(decoded):
            positions[decoded[position : position + 4]].append(position)

    while cursor < len(decoded):
        best_length = 0
        best_distance = 0

        if cursor + 4 <= len(decoded):
            key = decoded[cursor : cursor + 4]
            candidates = positions.get(key, ())
            for previous in reversed(candidates):
                distance = cursor - previous
                if distance > 0x1000:
                    break

                length = 4
                maximum = min(19, len(decoded) - cursor)
                while (
                    length < maximum
                    and decoded[cursor + length]
                    == decoded[cursor + length - distance]
                ):
                    length += 1

                # 0001h is reserved for an escaped literal marker.
                if distance == 1 and length == 4:
                    continue
                if length > best_length:
                    best_length = length
                    best_distance = distance
                    if length == maximum:
                        break

        if best_length >= 4:
            distance_field = 0 if best_distance == 0x1000 else best_distance
            token = ((best_length - 4) << 12) | distance_field
            output.append(marker)
            output.extend(token.to_bytes(2, "little"))
            for position in range(cursor, cursor + best_length):
                remember(position)
            cursor += best_length
            continue

        value = decoded[cursor]
        if value == marker:
            output.extend((marker, 1, 0))
        else:
            output.append(value)
        remember(cursor)
        cursor += 1

    return bytes(output)


def build_ass(template: bytes, decoded: bytes, marker: int) -> bytes:
    if len(decoded) > 0xFFFF:
        raise DecodeError("decoded ASS image is too large for its 16-bit header")
    if template[2] != marker or template[3] != 0:
        raise DecodeError("template ASS has an unexpected compression header")

    header = bytearray(template[:4])
    header.extend(len(decoded).to_bytes(2, "little"))
    return bytes(header) + compress_body(decoded, marker)


def build_one(
    spec: BuildSpec,
    input_dir: Path,
    output_dir: Path,
    reverse_table: dict[str, list[str]],
) -> Path:
    source_path = input_dir / spec.ass.source_name
    translation_path = input_dir / spec.translation_name
    template = source_path.read_bytes()
    rle_stream = decompress_ass(template, spec.ass.marker)
    final_image, literal_map = decompress_rle(rle_stream)
    translations = load_translation(translation_path)
    patched_final = patch_translations(
        rle_stream,
        final_image,
        literal_map,
        spec.ass,
        translations,
        reverse_table,
    )
    rebuilt_rle = compress_rle(patched_final, rle_stream)
    rebuilt = build_ass(template, rebuilt_rle, spec.ass.marker)

    if len(rebuilt) > MAX_LOADER_READ_SIZE:
        raise DecodeError(
            f"{spec.output_name}: {len(rebuilt)} bytes exceeds MAIN.EXE's "
            f"0x{MAX_LOADER_READ_SIZE:X}-byte load buffer"
        )

    # Do not write a file unless both MAIN.EXE decompression stages reproduce
    # the patched execution image exactly.
    verified_rle = decompress_ass(rebuilt, spec.ass.marker)
    verified_final, _ = decompress_rle(verified_rle)
    if verified_rle != rebuilt_rle or verified_final != patched_final:
        raise DecodeError(
            f"{spec.output_name}: LZ/RLE compression round-trip failed"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / spec.output_name
    output_path.write_bytes(rebuilt)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build OPEN_kor.ASS and END_kor.ASS from Korean JSON."
    )
    parser.add_argument(
        "--font-table",
        type=Path,
        default=Path("font_table-kor-jin.json"),
        help="Korean JSON font table (default: font_table-kor-jin.json)",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("."),
        help="directory containing ASS templates and Korean JSON (default: .)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="directory for generated ASS files (default: .)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    font_table = load_font_table(args.font_table)
    reverse_table = reverse_font_table(font_table)
    for spec in BUILD_SPECS:
        output_path = build_one(
            spec,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            reverse_table=reverse_table,
        )
        print(output_path)


if __name__ == "__main__":
    main()
