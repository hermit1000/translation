#!/usr/bin/env python3
"""Decode the compressed text blocks in OPEN.ASS and END.ASS."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AssSpec:
    source_name: str
    marker: int
    text_start: int
    text_end: int
    output_name: str


SPECS = (
    AssSpec(
        source_name="OPEN.ASS",
        marker=0x79,
        text_start=0x0A5F,
        text_end=0x14CB,
        output_name="OPEN_decoded_ASS_jpn.json",
    ),
    AssSpec(
        source_name="END.ASS",
        marker=0x6B,
        text_start=0x0989,
        text_end=0x0E68,
        output_name="END_decoded_ASS_jpn.json",
    ),
)

# Header layout:
#   0..1  entry/relocation metadata retained verbatim when rebuilding
#   2     compression marker
#   3     distance-bit adjustment (zero in OPEN.ASS and END.ASS)
#   4..5  decompressed byte count
# The decompressed image begins at runtime address 0006h.
COMPRESSED_DATA_OFFSET = 6
DECOMPRESSED_ADDRESS_BASE = 6


class DecodeError(ValueError):
    """Raised when an ASS stream or font-table entry is invalid."""


def decompress_ass(data: bytes, marker: int) -> bytes:
    """Implement the LZ back-reference routine found in MAIN.EXE."""
    if len(data) < COMPRESSED_DATA_OFFSET:
        raise DecodeError("ASS file is shorter than its six-byte header")
    if data[2] != marker or data[3] != 0:
        raise DecodeError(
            f"unexpected compression header {data[2]:02X} {data[3]:02X}; "
            f"expected {marker:02X} 00"
        )

    expected_size = int.from_bytes(data[4:6], "little")
    output = bytearray()
    cursor = COMPRESSED_DATA_OFFSET

    while len(output) < expected_size:
        if cursor >= len(data):
            raise DecodeError(
                f"compressed stream ended after {len(output)} of "
                f"{expected_size} decoded bytes"
            )

        token_offset = cursor
        value = data[cursor]
        cursor += 1

        if value != marker:
            output.append(value)
            continue

        if cursor + 2 > len(data):
            raise DecodeError(
                f"truncated token at source offset 0x{token_offset:X}"
            )

        token = data[cursor] | (data[cursor + 1] << 8)
        cursor += 2

        # MAIN.EXE treats 0001h as an escaped literal marker.
        if token == 1:
            output.append(marker)
            continue

        distance = token & 0x0FFF
        if distance == 0:
            distance = 0x1000
        length = (token >> 12) + 4

        if distance > len(output):
            raise DecodeError(
                f"invalid distance {distance} at source offset "
                f"0x{token_offset:X}; only {len(output)} bytes decoded"
            )

        # Append one byte at a time to preserve the overlapping-copy behavior
        # of REP MOVSB when length is greater than distance.
        for _ in range(length):
            output.append(output[-distance])

        if len(output) > expected_size:
            raise DecodeError(
                f"token at source offset 0x{token_offset:X} exceeds the "
                f"declared decoded size {expected_size}"
            )

    return bytes(output)


def load_font_table(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8") as font_file:
        table = json.load(font_file)

    if not isinstance(table, dict):
        raise DecodeError(f"{path}: the font table must be a JSON object")

    normalized: dict[str, str] = {}
    for code, character in table.items():
        normalized_code = str(code).upper()
        if (
            len(normalized_code) != 4
            or any(c not in "0123456789ABCDEF" for c in normalized_code)
            or not isinstance(character, str)
        ):
            raise DecodeError(f"{path}: invalid font-table entry {code!r}")
        normalized[normalized_code] = character
    return normalized


def decode_text(
    encoded: bytes,
    start_address: int,
    font_table: dict[str, str],
) -> dict[str, str]:
    """Split NUL-delimited strings and map every two-byte font code."""
    result: dict[str, str] = {}
    segment_start = 0

    for cursor in range(len(encoded) + 1):
        at_end = cursor == len(encoded)
        if not at_end and encoded[cursor] != 0:
            continue

        segment = encoded[segment_start:cursor]
        if segment:
            if len(segment) % 2:
                address = start_address + segment_start
                raise DecodeError(
                    f"odd-length text at address 0x{address:05X}: "
                    f"{len(segment)} bytes"
                )

            characters: list[str] = []
            for index in range(0, len(segment), 2):
                code = segment[index : index + 2].hex().upper()
                try:
                    characters.append(font_table[code])
                except KeyError as error:
                    address = start_address + segment_start + index
                    raise DecodeError(
                        f"font code {code} at address 0x{address:05X} "
                        "is missing from the font table"
                    ) from error

            first = start_address + segment_start
            last = start_address + cursor - 1
            result[f"{first:05X}={last:05X}"] = "".join(characters)

        segment_start = cursor + 1

    return result


def extract_one(
    spec: AssSpec,
    input_dir: Path,
    output_dir: Path,
    font_table: dict[str, str],
) -> Path:
    source_path = input_dir / spec.source_name
    decoded = decompress_ass(source_path.read_bytes(), spec.marker)

    slice_start = spec.text_start - DECOMPRESSED_ADDRESS_BASE
    slice_end = spec.text_end - DECOMPRESSED_ADDRESS_BASE + 1
    if slice_start < 0 or slice_end > len(decoded):
        raise DecodeError(
            f"{source_path}: text range 0x{spec.text_start:05X}-"
            f"0x{spec.text_end:05X} is outside the decoded image"
        )

    document = decode_text(
        decoded[slice_start:slice_end],
        spec.text_start,
        font_table,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / spec.output_name
    with output_path.open("w", encoding="utf-8", newline="\r\n") as output_file:
        json.dump(document, output_file, ensure_ascii=False, indent=4)
        output_file.write("\n")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decode OPEN.ASS and END.ASS into separate JSON documents."
    )
    parser.add_argument(
        "--font-table",
        type=Path,
        default=Path("font_table-jpn.json"),
        help="JSON font table (default: font_table-jpn.json)",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("."),
        help="directory containing OPEN.ASS and END.ASS (default: current directory)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="directory for generated JSON files (default: current directory)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    font_table = load_font_table(args.font_table)
    for spec in SPECS:
        output_path = extract_one(
            spec,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            font_table=font_table,
        )
        print(output_path)


if __name__ == "__main__":
    main()
