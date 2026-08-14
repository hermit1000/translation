#!/usr/bin/env python3
"""Encode Nobu5 PC-98 replacement graphics from binary_inputs-pc98."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from gspecific.nobu5.decode_graphics import (
    MAIN_PALETTE_00_8,
    PACK_SECTORS,
    SLOGO_OFFSETS,
    SOPEN_IMAGE_COUNT,
    SOPEN_PALETTE_8,
    decode_slogo_image,
    decode_sopen_image,
    encode_interleaved_planar,
    rotate_left,
)


class EncodeError(ValueError):
    pass


def packed_to_planar_triplet(chunk: bytes) -> bytes:
    b0, b1, b2, b3 = chunk
    first = b0 | b1 << 8
    second = b2 | b3 << 8
    second_low = second & 0xFF
    first_high = first >> 8
    first = (first & 0x00FF) | second_low << 8
    second = (second & 0xFF00) | first_high
    first = rotate_left(first, 4, 16)
    first = (first & 0xFF00) | rotate_left(first & 0xFF, 4, 8)
    first = rotate_left(first, 12, 16)
    second = rotate_left(second, 4, 16)
    second = (second & 0xFF00) | rotate_left(second & 0xFF, 4, 8)
    second = rotate_left(second, 4, 16)
    return bytes((first >> 8, first & 0xFF, second & 0xFF))


def build_planar_to_packed_maps() -> tuple[dict[bytes, tuple[int, int]], dict[int, tuple[int, int]]]:
    first_two: dict[bytes, tuple[int, int]] = {}
    third: dict[int, tuple[int, int]] = {}
    for b0 in range(0x100):
        for b2 in range(0x100):
            first_two.setdefault(packed_to_planar_triplet(bytes((b0, 0, b2, 0)))[:2], (b0, b2))
    for b1 in range(0x100):
        for b3 in range(0x100):
            third.setdefault(packed_to_planar_triplet(bytes((0, b1, 0, b3)))[2], (b1, b3))
    return first_two, third


def planar_to_slogo_packed(planar: bytes) -> bytes:
    if len(planar) % 3:
        raise EncodeError("SLOGO planar data size must be divisible by 3")
    first_two, third = build_planar_to_packed_maps()
    packed = bytearray()
    for offset in range(0, len(planar), 3):
        key = planar[offset : offset + 2]
        try:
            b0, b2 = first_two[key]
            b1, b3 = third[planar[offset + 2]]
        except KeyError as error:
            raise EncodeError(f"cannot pack planar triplet at 0x{offset:06X}") from error
        packed.extend((b0, b1, b2, b3))
    return bytes(packed)


def image_to_indices(
    png_path: Path,
    width: int,
    height: int,
    palette: list[tuple[int, int, int]] = SOPEN_PALETTE_8,
) -> bytes:
    with Image.open(png_path) as source:
        image = source.convert("RGB")

    if image.size != (width, height):
        raise EncodeError(
            f"{png_path}: image size is {image.width}x{image.height}, "
            f"expected {width}x{height}"
        )

    color_to_index = {color: index for index, color in enumerate(palette)}
    indices = bytearray()
    for position, color in enumerate(image.getdata()):
        try:
            indices.append(color_to_index[color])
        except KeyError as error:
            x = position % width
            y = position // width
            raise EncodeError(f"{png_path}: unsupported RGB color {color} at ({x}, {y})") from error
    return bytes(indices)


def image_to_sopen_groups(png_path: Path, width: int, height: int) -> tuple[list[int], bytes, bytes]:
    with Image.open(png_path) as source:
        image = source.convert("RGBA")

    if image.size != (width, height):
        raise EncodeError(
            f"{png_path}: image size is {image.width}x{image.height}, "
            f"expected {width}x{height}"
        )

    color_to_index = {color: index for index, color in enumerate(SOPEN_PALETTE_8)}
    groups_per_row = (width + 3) // 4
    groups: list[int] = []
    indices = bytearray(width * height)
    alpha = bytearray([255]) * (width * height)
    pixels = list(image.getdata())
    for y in range(height):
        for group_x in range(groups_per_row):
            pattern = 0
            for bit in range(4):
                x = group_x * 4 + bit
                if x >= width:
                    pattern |= (8 >> bit) << 12
                    continue
                position = y * width + x
                red, green, blue, opacity = pixels[position]
                try:
                    index = color_to_index[(red, green, blue)]
                except KeyError as error:
                    if opacity < 128:
                        index = 0
                    else:
                        raise EncodeError(
                            f"{png_path}: unsupported RGB color {(red, green, blue)} at ({x}, {y})"
                        ) from error
                indices[position] = index
                if opacity < 128:
                    pattern |= (8 >> bit) << 12
                    alpha[position] = 0
                for plane in range(3):
                    if index & (1 << plane):
                        pattern |= (8 >> bit) << (plane * 4)
            groups.append(pattern)
    return groups, bytes(indices), bytes(alpha)


def sopen_literal_bytes(pattern: int, repeat: int, patterns: tuple[int, ...]) -> bytes:
    if not 1 <= repeat <= 8:
        raise EncodeError("SOPEN literal repeat must be between 1 and 8")
    count_bits = repeat - 1
    if pattern == 0:
        return bytes((count_bits,))
    try:
        pattern_index = patterns.index(pattern)
    except ValueError:
        pattern_index = -1
    if pattern_index >= 0:
        return bytes((0x40 | pattern_index << 3 | count_bits,))
    low = pattern & 0xFF
    high = pattern >> 8
    if high == 0:
        return bytes((0x08 | count_bits, low))
    if pattern == ((low & 0x0F) | ((low & 0xF0) << 8)):
        return bytes((0x10 | count_bits, low))
    if pattern == low << 4:
        return bytes((0x20 | count_bits, low))
    if pattern == ((low & 0x0F) << 4 | ((low & 0xF0) << 8)):
        return bytes((0x28 | count_bits, low))
    if low == 0:
        return bytes((0x30 | count_bits, high))
    return bytes((0x38 | count_bits, low, high))


def choose_sopen_patterns(groups: list[int]) -> tuple[int, ...]:
    counts: dict[int, int] = {}
    for pattern in groups:
        if pattern:
            counts[pattern] = counts.get(pattern, 0) + 1
    frequent = sorted(counts, key=lambda pattern: (-counts[pattern], pattern))[:8]
    return tuple(frequent + [0] * (8 - len(frequent)))


def encode_sopen_stream(groups: list[int], width: int, height: int, patterns: tuple[int, ...]) -> bytes:
    groups_per_row = (width + 3) // 4
    if len(groups) != groups_per_row * height:
        raise EncodeError("SOPEN group count does not match dimensions")

    encoded = bytearray()
    rows = [groups[row * groups_per_row : (row + 1) * groups_per_row] for row in range(height)]
    for row_index, row in enumerate(rows):
        dp: list[tuple[int, bytearray] | None] = [None] * (groups_per_row + 1)
        dp[0] = (0, bytearray())
        for position in range(groups_per_row):
            state = dp[position]
            if state is None:
                continue
            cost, data = state

            pattern = row[position]
            max_literal = min(8, groups_per_row - position)
            repeat = 0
            while repeat < max_literal and row[position + repeat] == pattern:
                repeat += 1
            for literal_count in range(1, repeat + 1):
                command = sopen_literal_bytes(pattern, literal_count, patterns)
                target = position + literal_count
                candidate = data + command
                candidate_cost = cost + len(command)
                if dp[target] is None or candidate_cost < dp[target][0]:
                    dp[target] = (candidate_cost, candidate)

            for selector in range(1, 5):
                if position >= selector:
                    repeat = 0
                    limit = min(16, groups_per_row - position)
                    while repeat < limit and row[position + repeat] == row[position + repeat - selector]:
                        repeat += 1
                    for copy_count in range(1, repeat + 1):
                        command = bytes((0x80 | ((selector - 1) << 4) | (copy_count - 1),))
                        target = position + copy_count
                        candidate = data + command
                        if dp[target] is None or cost + 1 < dp[target][0]:
                            dp[target] = (cost + 1, candidate)

                if row_index >= selector:
                    source_row = rows[row_index - selector]
                    repeat = 0
                    limit = min(16, groups_per_row - position)
                    while repeat < limit and row[position + repeat] == source_row[position + repeat]:
                        repeat += 1
                    for copy_count in range(1, repeat + 1):
                        command = bytes((0xC0 | ((selector - 1) << 4) | (copy_count - 1),))
                        target = position + copy_count
                        candidate = data + command
                        if dp[target] is None or cost + 1 < dp[target][0]:
                            dp[target] = (cost + 1, candidate)

        if dp[groups_per_row] is None:
            raise EncodeError(f"SOPEN row {row_index} cannot be encoded")
        encoded.extend(dp[groups_per_row][1])
    return bytes(encoded)


def encode_sopen_png(png_path: Path, width: int, height: int) -> tuple[bytes, bytes, bytes, bytes]:
    groups, indices, alpha = image_to_sopen_groups(png_path, width, height)
    patterns = choose_sopen_patterns(groups)
    stream = encode_sopen_stream(groups, width, height, patterns)
    encoded = (
        width.to_bytes(2, "little")
        + height.to_bytes(2, "little")
        + b"".join(pattern.to_bytes(2, "little") for pattern in patterns)
        + stream
    )
    decoded_width, decoded_height, planar, decoded_indices, decoded_alpha, stream_end = decode_sopen_image(
        encoded, 0
    )
    if (decoded_width, decoded_height) != (width, height):
        raise EncodeError("encoded SOPEN dimensions do not round-trip")
    if stream_end != len(encoded):
        raise EncodeError("encoded SOPEN stream has trailing data after round-trip")
    if decoded_indices != indices or decoded_alpha != alpha:
        raise EncodeError(f"{png_path}: encoded SOPEN pixels do not round-trip")
    return encoded, planar, indices, alpha


def encode_slogo_stream(packed: bytes, width: int, height: int) -> bytes:
    groups_per_row = (width + 3) // 4
    expected_size = groups_per_row * height * 2
    if len(packed) != expected_size:
        raise EncodeError(f"packed SLOGO size is {len(packed)}, expected {expected_size}")

    # The high nibble of the second byte in each packed word is not part of the
    # decoded pixels for this GRPDRV layout. It doubles as the literal repeat
    # count when the word is emitted directly, so choose it during compression
    # instead of fixing it before the LZ pass.
    word_keys = [
        (packed[offset], packed[offset + 1] & 0x0F)
        for offset in range(0, len(packed), 2)
    ]
    ring = [[b"\x00\x00"] * groups_per_row for _ in range(5)]
    encoded = bytearray()

    def make_word(word_key: tuple[int, int], repeat: int) -> bytes:
        return bytes((word_key[0], word_key[1] | ((repeat - 1) << 4)))

    def word_key(word: bytes) -> tuple[int, int]:
        return word[0], word[1] & 0x0F

    def horizontal_copy_words(prefix: list[bytes], position: int, selector: int, count: int) -> list[bytes]:
        output = list(prefix)
        for index in range(count):
            output.append(output[position - selector + index])
        return output[position:]

    for row_index in range(height):
        slot = row_index % 5
        row = word_keys[row_index * groups_per_row : (row_index + 1) * groups_per_row]
        dp: list[tuple[int, bytearray, list[bytes]] | None] = [None] * (groups_per_row + 1)
        dp[0] = (0, bytearray(), [])

        for position in range(groups_per_row):
            state = dp[position]
            if state is None:
                continue
            cost, data, output_words = state

            word = row[position]
            literal_limit = min(8, groups_per_row - position)
            literal_count = 0
            while literal_count < literal_limit and row[position + literal_count] == word:
                literal_count += 1
            for repeat in range(1, literal_count + 1):
                packed_word = make_word(word, repeat)
                target = position + repeat
                candidate = data + bytes((packed_word[1], packed_word[0]))
                candidate_cost = cost + 2
                if dp[target] is None or candidate_cost < dp[target][0]:
                    dp[target] = (
                        candidate_cost,
                        candidate,
                        output_words + [packed_word] * repeat,
                    )

            for selector in range(1, 5):
                if position >= selector:
                    count = 0
                    limit = min(16, groups_per_row - position)
                    copied_prefix = list(output_words)
                    while count < limit:
                        source_word = copied_prefix[position - selector + count]
                        if word_key(source_word) != row[position + count]:
                            break
                        copied_prefix.append(source_word)
                        count += 1
                    for copy_count in range(1, count + 1):
                        command = 0x80 | ((selector - 1) << 4) | (copy_count - 1)
                        candidate = data + bytes((command,))
                        target = position + copy_count
                        if dp[target] is None or cost + 1 < dp[target][0]:
                            dp[target] = (
                                cost + 1,
                                candidate,
                                output_words + horizontal_copy_words(output_words, position, selector, copy_count),
                            )

                if row_index >= selector:
                    source_row = ring[(slot - selector) % 5]
                    count = 0
                    limit = min(16, groups_per_row - position)
                    while count < limit and word_key(source_row[position + count]) == row[position + count]:
                        count += 1
                    for copy_count in range(1, count + 1):
                        command = 0xC0 | ((selector - 1) << 4) | (copy_count - 1)
                        candidate = data + bytes((command,))
                        target = position + copy_count
                        if dp[target] is None or cost + 1 < dp[target][0]:
                            dp[target] = (
                                cost + 1,
                                candidate,
                                output_words + [source_row[position + index] for index in range(copy_count)],
                            )

        if dp[groups_per_row] is None:
            raise EncodeError(f"row {row_index} cannot be encoded with SLOGO commands")
        encoded.extend(dp[groups_per_row][1])
        ring[slot] = dp[groups_per_row][2]

    return bytes(encoded)


def encode_slogo_png(
    png_path: Path,
    width: int,
    height: int,
    palette: list[tuple[int, int, int]] = SOPEN_PALETTE_8,
) -> tuple[bytes, bytes, bytes]:
    indices = image_to_indices(png_path, width, height, palette)
    planar = encode_interleaved_planar(indices, width, height, 3)
    packed = planar_to_slogo_packed(planar)
    stream = encode_slogo_stream(packed, width, height)
    encoded = width.to_bytes(2, "little") + height.to_bytes(2, "little") + stream

    decoded_width, decoded_height, _, decoded_indices, stream_end = decode_slogo_image(
        encoded, 0, len(encoded)
    )
    if (decoded_width, decoded_height) != (width, height):
        raise EncodeError("encoded SLOGO dimensions do not round-trip")
    if stream_end != len(encoded):
        raise EncodeError("encoded SLOGO stream has trailing data after round-trip")
    if decoded_indices != indices:
        raise EncodeError(f"{png_path}: encoded SLOGO pixels do not round-trip")
    return encoded, planar, indices


def encode_slogo_archive(workspace: Path, *, all_artifacts: bool = False) -> int:
    source_path = workspace / "jpn-pc98" / "SLOGO.NB5"
    input_dir = workspace / "binary_inputs-pc98" / "SLOGO.NB5"
    if not source_path.is_file():
        raise FileNotFoundError(f"missing source file: {source_path}")
    if not input_dir.is_dir():
        return 0

    source = bytearray(source_path.read_bytes())
    ends = SLOGO_OFFSETS[1:] + (len(source),)
    records = {
        f"{start:06x}": {
            "index": index,
            "start": start,
            "end": end,
            "size": end - start,
        }
        for index, (start, end) in enumerate(zip(SLOGO_OFFSETS, ends))
    }

    entries = []
    encoded_count = 0
    for png_path in sorted(input_dir.glob("*.kor.png")):
        stem = png_path.name.removesuffix(".kor.png")
        if stem not in records:
            raise EncodeError(f"{png_path}: no matching SLOGO record offset")
        record = records[stem]
        start = int(record["start"])
        end = int(record["end"])
        original_size = int(record["size"])
        width, height, _, _, _ = decode_slogo_image(bytes(source), start, end)

        encoded, planar, indices = encode_slogo_png(png_path, width, height)
        if len(encoded) > original_size:
            raise EncodeError(
                f"{png_path}: encoded size {len(encoded)} exceeds original record size {original_size}"
            )

        padding_size = original_size - len(encoded)
        replacement = encoded + b"\x00" * padding_size
        source[start:end] = replacement
        replacement_path = png_path.with_name(f"{stem}.kor.bin")
        replacement_path.write_bytes(replacement)
        files = {
            "png": png_path.name,
            "replacement": replacement_path.name,
        }
        cmp_path = png_path.with_name(f"{stem}.cmp.kor.bin")
        planar_path = png_path.with_name(f"{stem}.pln.kor.bin")
        indices_path = png_path.with_name(f"{stem}.idx.kor.bin")
        if all_artifacts:
            cmp_path.write_bytes(encoded)
            planar_path.write_bytes(planar)
            indices_path.write_bytes(indices)
            files.update(
                {
                    "compressed": cmp_path.name,
                    "planar": planar_path.name,
                    "pixels": indices_path.name,
                }
            )
        else:
            cmp_path.unlink(missing_ok=True)
            planar_path.unlink(missing_ok=True)
            indices_path.unlink(missing_ok=True)

        entries.append(
            {
                "offset": f"0x{start:06X}",
                "record_index": record["index"],
                "width": width,
                "height": height,
                "original_size": original_size,
                "compressed_size": len(encoded),
                "padding_size": padding_size,
                "output_size": original_size,
                "files": files,
            }
        )
        encoded_count += 1
        print(
            f"{png_path}: compressed={len(encoded)} "
            f"padding={padding_size} record={original_size}"
        )

    if encoded_count:
        output_path = input_dir / "SLOGO.NB5"
        output_path.write_bytes(source)
        report = {
            "source": source_path.name,
            "format": "Nobu5 SLOGO GRPDRV-lz replacement records",
            "output": output_path.name,
            "entries": entries,
        }
        (input_dir / "encode_log.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )
    return encoded_count


def encode_pack_archive(workspace: Path, *, all_artifacts: bool = False) -> int:
    source_path = workspace / "jpn-pc98" / "PACK.NB5"
    input_dir = workspace / "binary_inputs-pc98" / "PACK.NB5"
    if not source_path.is_file():
        raise FileNotFoundError(f"missing source file: {source_path}")
    if not input_dir.is_dir():
        return 0

    source = bytearray(source_path.read_bytes())
    starts = [sector * 0x200 for sector in PACK_SECTORS]
    ends = starts[1:] + [len(source)]
    records = {
        f"{start:06x}": {
            "index": index,
            "sector": PACK_SECTORS[index],
            "start": start,
            "end": end,
            "size": end - start,
        }
        for index, (start, end) in enumerate(zip(starts, ends))
    }

    entries = []
    json_entries = []
    skipped_entries = []
    encoded_count = 0
    for png_path in sorted(input_dir.glob("*.kor.png")):
        stem = png_path.name.removesuffix(".kor.png")
        if stem not in records:
            raise EncodeError(f"{png_path}: no matching PACK record offset")
        record = records[stem]
        start = int(record["start"])
        end = int(record["end"])
        original_size = int(record["size"])
        width, height, _, _, _ = decode_slogo_image(bytes(source), start, end)

        encoded, planar, indices = encode_slogo_png(png_path, width, height, MAIN_PALETTE_00_8)
        if len(encoded) > original_size:
            skipped_entries.append(
                {
                    "offset": f"0x{start:06X}",
                    "record_index": record["index"],
                    "sector": f"0x{int(record['sector']):03X}",
                    "width": width,
                    "height": height,
                    "original_size": original_size,
                    "compressed_size": len(encoded),
                    "excess_size": len(encoded) - original_size,
                    "png": png_path.name,
                }
            )
            print(
                f"{png_path}: skipped compressed={len(encoded)} "
                f"exceeds record={original_size} by {len(encoded) - original_size}"
            )
            continue

        padding_size = original_size - len(encoded)
        replacement = encoded + b"\x00" * padding_size
        source[start:end] = replacement
        replacement_path = png_path.with_name(f"{stem}.kor.bin")
        replacement_path.write_bytes(replacement)
        files = {
            "png": png_path.name,
            "replacement": replacement_path.name,
        }

        cmp_path = png_path.with_name(f"{stem}.cmp.kor.bin")
        planar_path = png_path.with_name(f"{stem}.pln.kor.bin")
        indices_path = png_path.with_name(f"{stem}.idx.kor.bin")
        if all_artifacts:
            cmp_path.write_bytes(encoded)
            planar_path.write_bytes(planar)
            indices_path.write_bytes(indices)
            files.update(
                {
                    "compressed": cmp_path.name,
                    "planar": planar_path.name,
                    "pixels": indices_path.name,
                }
            )
        else:
            cmp_path.unlink(missing_ok=True)
            planar_path.unlink(missing_ok=True)
            indices_path.unlink(missing_ok=True)

        entry = {
            "offset": f"0x{start:06X}",
            "record_index": record["index"],
            "sector": f"0x{int(record['sector']):03X}",
            "width": width,
            "height": height,
            "original_size": original_size,
            "compressed_size": len(encoded),
            "padding_size": padding_size,
            "output_size": original_size,
            "files": files,
        }
        entries.append(entry)
        json_entries.append(
            {
                "start": start,
                "end": end,
                "replacement": replacement_path.name,
            }
        )
        encoded_count += 1
        print(
            f"{png_path}: compressed={len(encoded)} "
            f"padding={padding_size} record={original_size}"
        )

    if encoded_count:
        output_path = input_dir / "PACK.NB5"
        output_path.write_bytes(source)
        write_binary_input_json(workspace, "PACK.NB5", json_entries)
        report = {
            "source": source_path.name,
            "format": "Nobu5 PACK GRPDRV-lz replacement records",
            "output": output_path.name,
            "output_mode": "fixed-sector-record",
            "entries": entries,
            "skipped_entries": skipped_entries,
        }
        (input_dir / "encode_log.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )
    return encoded_count


def write_binary_input_json(
    workspace: Path,
    target_name: str,
    entries: list[dict[str, object]],
) -> None:
    if not entries:
        return
    script_dir = workspace / "script-pc98"
    script_dir.mkdir(parents=True, exist_ok=True)
    binary_input = {
        f"{int(entry['start']):05X}={int(entry['end']) - 1:05X}": f"{target_name}/{entry['replacement']}"
        for entry in entries
    }
    json_path = script_dir / f"{target_name}_kor.json"
    json_path.write_text(
        json.dumps({"binary_input": binary_input}, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
        newline="\r\n",
    )
    jpn_path = script_dir / f"{target_name}_jpn.json"
    jpn_path.write_text("{}\n", encoding="utf-8", newline="\r\n")


def find_sopen_records(source: bytes) -> list[dict[str, int]]:
    records = []
    start = 0
    while start < len(source):
        width, height, _, _, _, end = decode_sopen_image(source, start)
        records.append(
            {
                "index": len(records),
                "start": start,
                "end": end,
                "size": end - start,
                "width": width,
                "height": height,
            }
        )
        start = end
    if len(records) != SOPEN_IMAGE_COUNT:
        raise EncodeError(f"SOPEN.NB5 contains {len(records)} records, expected {SOPEN_IMAGE_COUNT}")
    return records


def encode_sopen_archive(workspace: Path, *, all_artifacts: bool = False) -> int:
    source_path = workspace / "jpn-pc98" / "SOPEN.NB5"
    input_dir = workspace / "binary_inputs-pc98" / "SOPEN.NB5"
    if not source_path.is_file():
        raise FileNotFoundError(f"missing source file: {source_path}")
    if not input_dir.is_dir():
        return 0

    source = bytearray(source_path.read_bytes())
    record_list = find_sopen_records(bytes(source))
    records = {
        f"{record['start']:06x}": record
        for record in record_list
    }

    entries = []
    json_entries = []
    encoded_count = 0
    for png_path in sorted(input_dir.glob("*.kor.png")):
        stem = png_path.name.removesuffix(".kor.png")
        if stem not in records:
            raise EncodeError(f"{png_path}: no matching SOPEN record offset")
        record = records[stem]
        start = int(record["start"])
        end = int(record["end"])
        original_size = int(record["size"])
        width = int(record["width"])
        height = int(record["height"])

        encoded, planar, indices, alpha = encode_sopen_png(png_path, width, height)
        if len(encoded) > original_size:
            raise EncodeError(
                f"{png_path}: encoded size {len(encoded)} exceeds original record size {original_size}"
            )

        padding_size = original_size - len(encoded)
        replacement = encoded + b"\x00" * padding_size
        source[start:end] = replacement
        replacement_path = png_path.with_name(f"{stem}.kor.bin")
        replacement_path.write_bytes(replacement)
        files = {
            "png": png_path.name,
            "replacement": replacement_path.name,
        }

        cmp_path = png_path.with_name(f"{stem}.cmp.kor.bin")
        planar_path = png_path.with_name(f"{stem}.pln.kor.bin")
        indices_path = png_path.with_name(f"{stem}.idx.kor.bin")
        alpha_path = png_path.with_name(f"{stem}.alpha.kor.bin")
        if all_artifacts:
            cmp_path.write_bytes(encoded)
            planar_path.write_bytes(planar)
            indices_path.write_bytes(indices)
            alpha_path.write_bytes(alpha)
            files.update(
                {
                    "compressed": cmp_path.name,
                    "planar": planar_path.name,
                    "pixels": indices_path.name,
                    "alpha": alpha_path.name,
                }
            )
        else:
            cmp_path.unlink(missing_ok=True)
            planar_path.unlink(missing_ok=True)
            indices_path.unlink(missing_ok=True)
            alpha_path.unlink(missing_ok=True)

        entry = {
            "offset": f"0x{start:06X}",
            "record_index": record["index"],
            "width": width,
            "height": height,
            "original_size": original_size,
            "compressed_size": len(encoded),
            "padding_size": padding_size,
            "output_size": original_size,
            "files": files,
        }
        entries.append(entry)
        json_entries.append(
            {
                "start": start,
                "end": end,
                "replacement": replacement_path.name,
            }
        )
        encoded_count += 1
        print(
            f"{png_path}: compressed={len(encoded)} "
            f"padding={padding_size} record={original_size}"
        )

    if encoded_count:
        output_path = input_dir / "SOPEN.NB5"
        output_path.write_bytes(source)
        write_binary_input_json(workspace, "SOPEN.NB5", json_entries)
        report = {
            "source": source_path.name,
            "format": "Nobu5 SOPEN mask-overlay replacement records",
            "output": output_path.name,
            "output_mode": "fixed-record",
            "entries": entries,
        }
        (input_dir / "encode_log.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )
    return encoded_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("c:/work_han/workspace5"),
        help="workspace containing jpn-pc98 and binary_inputs-pc98 (default: c:/work_han/workspace5)",
    )
    parser.add_argument(
        "--all-artifacts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="keep planar and indexed intermediate artifacts (default: no-all-artifacts)",
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    slogo_count = encode_slogo_archive(workspace, all_artifacts=args.all_artifacts)
    sopen_count = encode_sopen_archive(workspace, all_artifacts=args.all_artifacts)
    pack_count = encode_pack_archive(workspace, all_artifacts=args.all_artifacts)
    print(f"encoded {slogo_count} SLOGO image(s)")
    print(f"encoded {sopen_count} SOPEN image(s)")
    print(f"encoded {pack_count} PACK image(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
