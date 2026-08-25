#!/usr/bin/env python3
"""Decode one MES file or a directory tree into structured Japanese JSON.

With no output path, print a diagnostic lexical decode of one file. Unknown
commands are retained instead of being assigned guessed meanings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


COMMAND_NAMES = {
    0xA6: "SET_RECT",
    0xAA: "F6_0B_AND_CURSOR_RESET",
    0xB7: "DISPLAY_CONFIG",
    0xB9: "DEFINE_MACRO",
    0xBA: "CALL_BUILTIN",
    0xBB: "REPEAT_BLOCK",
    0xC9: "LOAD_GPC",
    0xCD: "GRAPH_OP",
    0xCF: "APPLY_GPC_OPTIONS",
    0xD0: "AUDIO",
    0xD1: "F3_STATE",
}

SPECIAL_SJIS = {
    0x8197: "CONTROL_FULLWIDTH_AT",
    0x8190: "CONTROL_FULLWIDTH_DOLLAR",
    0x816F: "BLOCK_OPEN",
    0x8170: "BLOCK_CLOSE",
}


def is_sjis_lead(value: int) -> bool:
    return 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC


def is_sjis_trail(value: int) -> bool:
    return 0x40 <= value <= 0x7E or 0x80 <= value <= 0xFC


def decode_pair(first: int, second: int) -> str:
    return bytes((first, second)).decode("cp932", errors="replace")


def make_token(
    offset: int,
    size: int,
    raw: bytes,
    token_type: str,
    value: str | int,
    **extra: Any,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "offset": offset,
        "size": size,
        "bytes": list(raw),
        "type": token_type,
        "value": value,
    }
    result.update(extra)
    return result


def decode_mes(data: bytes) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    offset = 0

    while offset < len(data):
        first = data[offset]
        second = data[offset + 1] if offset + 1 < len(data) else None

        previous = result[-1] if result else None
        if (
            previous
            and previous["type"] == "command"
            and previous["value"] == "AUDIO"
            and second is not None
            and (first | 0x20) == 0x73
            and (second | 0x20) == 0x65
        ):
            result.append(make_token(offset, 2, data[offset : offset + 2], "keyword", "se"))
            offset += 2
            continue

        if second is not None and first == 0xFF and second in (0xFE, 0xFF):
            name = "END_FFFF" if second == 0xFF else "END_FFFE"
            result.append(make_token(offset, 2, data[offset : offset + 2], "end", name))
            offset += 2
            continue

        if first == 0x22:
            end = data.find(b'"', offset + 1)
            closed = end >= 0
            if not closed:
                end = len(data)
            size = end - offset + (1 if closed else 0)
            content = data[offset + 1 : end].decode("cp932", errors="replace")
            result.append(
                make_token(
                    offset,
                    size,
                    data[offset : offset + size],
                    "quoted",
                    content,
                    closed=closed,
                )
            )
            offset += size
            continue

        if second is not None and is_sjis_lead(first) and is_sjis_trail(second):
            word = first << 8 | second
            text = decode_pair(first, second)
            if word in SPECIAL_SJIS:
                result.append(
                    make_token(
                        offset,
                        2,
                        data[offset : offset + 2],
                        "control",
                        SPECIAL_SJIS[word],
                        text=text,
                    )
                )
            else:
                result.append(
                    make_token(
                        offset,
                        2,
                        data[offset : offset + 2],
                        "text",
                        text,
                        encoding="shift_jis",
                    )
                )
            offset += 2
            continue

        if 0x2D <= first <= 0x7F:
            expanded = bytes((0x82, (first + 0x72) & 0xFF))
            result.append(
                make_token(
                    offset,
                    1,
                    data[offset : offset + 1],
                    "text",
                    expanded.decode("cp932", errors="replace"),
                    encoding="adv98-compressed-sjis",
                    expandedBytes=list(expanded),
                )
            )
            offset += 1
            continue

        if 0xA6 <= first <= 0xD8:
            result.append(
                make_token(
                    offset,
                    1,
                    data[offset : offset + 1],
                    "command",
                    COMMAND_NAMES.get(first, f"CMD_{first:02X}"),
                )
            )
            offset += 1
            continue

        if 0xA0 <= first <= 0xA4:
            result.append(
                make_token(offset, 1, data[offset : offset + 1], "boundary", f"BOUNDARY_{first:02X}")
            )
            offset += 1
            continue

        if first == 0xA5:
            result.append(make_token(offset, 1, data[offset : offset + 1], "control", "CONTROL_A5"))
            offset += 1
            continue

        # ADV98 message streams use 0x08/0x0C/0x0D followed by a one-byte parameter
        # for internal display/control operations.  The parameter often falls
        # in the compressed-SJIS printable range; treating it as text produces
        # bogus trailing kana such as ``ぁ`` or ``っ`` after a sentence.
        if first in (0x08, 0x0C, 0x0D) and second is not None:
            result.append(
                make_token(
                    offset,
                    2,
                    data[offset : offset + 2],
                    "control",
                    f"CONTROL_{first:02X}",
                    parameter=second,
                )
            )
            offset += 2
            continue

        if 0x23 <= first <= 0x27:
            result.append(
                make_token(
                    offset,
                    1,
                    data[offset : offset + 1],
                    "argument",
                    first - 0x23,
                    form="small-constant",
                )
            )
            offset += 1
            continue

        if first == 0x28 and second is not None:
            result.append(
                make_token(
                    offset,
                    2,
                    data[offset : offset + 2],
                    "argument",
                    second,
                    form="byte-constant",
                )
            )
            offset += 2
            continue

        if 0x29 <= first <= 0x2C and offset + 2 < len(data):
            packed = data[offset + 1] << 8 | data[offset + 2]
            kind = first - 0x29
            value = kind << 14 | packed >> 1
            result.append(
                make_token(
                    offset,
                    3,
                    data[offset : offset + 3],
                    "argument",
                    value,
                    form="tagged-reference",
                    kind=kind,
                    packed=packed,
                )
            )
            offset += 3
            continue

        name = "CONTROL_21" if first == 0x21 else f"CONTROL_{first:02X}"
        result.append(make_token(offset, 1, data[offset : offset + 1], "control", name))
        offset += 1

    return result


def format_text(tokens: list[dict[str, Any]]) -> str:
    lines = []
    for item in tokens:
        offset = f'{item["offset"]:05X}'
        raw = " ".join(f"{value:02X}" for value in item["bytes"]).ljust(12)
        value = item["value"]
        rendered = f"0x{value:04X}" if isinstance(value, int) else json.dumps(value, ensure_ascii=False)
        lines.append(f'{offset}  {raw}  {item["type"]:<9}  {rendered}')
    return "\n".join(lines)


def make_readable_records(tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    index = 0

    while index < len(tokens):
        current = tokens[index]

        if current["type"] == "text":
            group = [current]
            end = current["offset"] + current["size"]
            index += 1
            while index < len(tokens):
                candidate = tokens[index]
                if candidate["type"] != "text" or candidate["offset"] != end:
                    break
                group.append(candidate)
                end += candidate["size"]
                index += 1
            raw = [byte for item in group for byte in item["bytes"]]
            records.append(
                {
                    "type": "text",
                    "offset": f'{group[0]["offset"]:05X}',
                    "end": f"{end - 1:05X}",
                    "text": "".join(str(item["value"]) for item in group),
                    "raw_hex": " ".join(f"{byte:02X}" for byte in raw),
                    "encodings": sorted({item.get("encoding", "unknown") for item in group}),
                    "translation_candidate": len(group) >= 2,
                }
            )
            continue

        if current["type"] == "command":
            arguments = []
            cursor = index + 1
            while cursor < len(tokens) and tokens[cursor]["type"] in {
                "argument",
                "quoted",
                "keyword",
            }:
                argument = tokens[cursor]
                arguments.append(
                    {
                        "offset": f'{argument["offset"]:05X}',
                        "type": argument["type"],
                        "value": argument["value"],
                        "raw_hex": " ".join(f"{byte:02X}" for byte in argument["bytes"]),
                    }
                )
                cursor += 1
            records.append(
                {
                    "type": "command",
                    "offset": f'{current["offset"]:05X}',
                    "opcode": f'{current["bytes"][0]:02X}',
                    "name": current["value"],
                    "arguments": arguments,
                }
            )
            index = cursor
            continue

        records.append(
            {
                "type": current["type"],
                "offset": f'{current["offset"]:05X}',
                "value": current["value"],
                "raw_hex": " ".join(f"{byte:02X}" for byte in current["bytes"]),
            }
        )
        index += 1

    return records


def diagnostic_main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="MES file to decode")
    parser.add_argument("--json", action="store_true", help="write structured JSON")
    parser.add_argument(
        "--readable-json",
        action="store_true",
        help="group adjacent text and command arguments for human inspection",
    )
    parser.add_argument(
        "--dialogue-json",
        action="store_true",
        help="write only multi-character translation candidates",
    )
    args = parser.parse_args()

    data = args.input.read_bytes()
    tokens = decode_mes(data)
    readable_records = make_readable_records(tokens)
    if args.dialogue_json:
        candidates = [
            {
                "offset": item["offset"],
                "end": item["end"],
                "text": item["text"],
                "raw_hex": item["raw_hex"],
                "encodings": item["encodings"],
            }
            for item in readable_records
            if item["type"] == "text" and item["translation_candidate"]
        ]
        print(
            json.dumps(
                {
                    "source": str(args.input.resolve()),
                    "size": len(data),
                    "warning": (
                        "Candidate list only. Unknown command schemas can still cause false positives; "
                        "do not use this file for automatic reinsertion yet."
                    ),
                    "candidate_count": len(candidates),
                    "dialogue_candidates": candidates,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.readable_json:
        print(
            json.dumps(
                {
                    "source": str(args.input.resolve()),
                    "size": len(data),
                    "warning": (
                        "This is a provisional lexical decode. Unknown command schemas can still make "
                        "isolated text candidates false positives."
                    ),
                    "legend": {
                        "text": "Adjacent decoded characters; translation_candidate is only a heuristic.",
                        "command": "MES opcode followed by immediately adjacent recognized arguments.",
                        "boundary": "One-byte parser boundary A0-A4.",
                        "control": "Non-printing or not-yet-understood control token.",
                        "end": "FFFF or FFFE interpreter terminator.",
                    },
                    "records": readable_records,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.json:
        print(
            json.dumps(
                {"source": str(args.input.resolve()), "size": len(data), "tokens": tokens},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(format_text(tokens))
    return 0


PACKAGE_DIR = Path(__file__).resolve().parent


def load_definition(name: str) -> dict[str, Any]:
    return json.loads((PACKAGE_DIR / name).read_text(encoding="utf-8"))


def verify_tokens(data: bytes, tokens: list[dict[str, Any]]) -> None:
    rebuilt = bytes(byte for token in tokens for byte in token["bytes"])
    if rebuilt != data:
        raise ValueError("decoded tokens do not reconstruct the original MES bytes")


def annotate_records(records: list[dict[str, Any]]) -> None:
    controls = load_definition("control_codes.json")["controls"]
    macros = load_definition("macro_catalog.json")["macros"]
    for record in records:
        if record["type"] == "text":
            record["original"] = record.pop("text")
        elif record["type"] == "control":
            definition = controls.get(record.get("raw_hex", "").replace(" ", ""))
            if definition:
                record["display"] = definition["display"]
                record["editable"] = definition["editable"]
        elif record["type"] == "command" and record["name"] == "CALL_BUILTIN":
            arguments = record["arguments"]
            if arguments and isinstance(arguments[0]["value"], int):
                slot = f'{arguments[0]["value"]:02X}'
                definition = macros.get(slot)
                record["macro_slot"] = slot
                if definition:
                    record["macro_name"] = definition["name"]
                    record["macro_category"] = definition["category"]
                    if "original" in definition:
                        record["macro_preview"] = definition["original"]


def decode_document(source: Path, source_name: str) -> dict[str, Any]:
    data = source.read_bytes()
    tokens = decode_mes(data)
    verify_tokens(data, tokens)
    records = make_readable_records(tokens)
    annotate_records(records)
    return {
        "format": "dob1-adv98-mes-jpn-v1",
        "language": "jpn",
        "source": source_name,
        "source_size": len(data),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "warning": "Provisional lexical decode; review translation candidates manually.",
        "text_record_count": sum(r["type"] == "text" for r in records),
        "translation_candidate_count": sum(
            r["type"] == "text" and r["translation_candidate"] for r in records
        ),
        "records": records,
    }


def write_decoded_json(input_path: Path, output_path: Path, force: bool) -> int:
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    if input_path.is_file():
        sources = [(input_path, Path(input_path.name))]
        destinations = [
            output_path
            if output_path.suffix.lower() == ".json"
            else output_path / f"{input_path.name}_jpn.json"
        ]
    else:
        sources = [
            (path, path.relative_to(input_path))
            for path in sorted(input_path.rglob("*"))
            if path.is_file() and path.suffix.upper() == ".MES"
        ]
        destinations = [
            output_path / relative.parent / f"{relative.name}_jpn.json"
            for _, relative in sources
        ]
    if not sources:
        raise ValueError(f"no MES files found: {input_path}")

    totals = {"files_written": 0, "text_records": 0, "translation_candidates": 0}
    for (source, relative), destination in zip(sources, destinations):
        if destination.exists() and not force:
            raise FileExistsError(f"output exists; pass --force: {destination}")
        document = decode_document(source, relative.as_posix())
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        totals["files_written"] += 1
        totals["text_records"] += document["text_record_count"]
        totals["translation_candidates"] += document["translation_candidate_count"]
    print(json.dumps(totals, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--readable-json", action="store_true")
    parser.add_argument("--dialogue-json", action="store_true")
    args = parser.parse_args()
    if args.output is None:
        return diagnostic_main()
    return write_decoded_json(args.input, args.output, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
