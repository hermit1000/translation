#!/usr/bin/env python3
"""Encode Nobunaga Zenkokuban PC-98 *.kor.png workspace images."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gspecific.image_workspace import ImageWorkspace
from gspecific.nobu2.decode_graphics import (
    ODAMAIN_COUNT,
    ODAMAIN_RECORD_SIZE,
    ODAMAIN_TABLE_OFFSET,
    PAK_SPECS,
    hex_offset,
)
from gspecific.nobu2.make_korean_graphics import build_all as build_korean_graphics
from gspecific.nobu2.make_map_graphics import build_all as build_map_graphics
from gspecific.nobu2.pc98_image_codec import encode_pak, image_to_planar
from gspecific.nobu2.prepare_graphics_384k import prepare_all as prepare_graphics_384k

DOS_PADDING = 0x1A


def offset_pngs(directory: Path, *, recursive: bool = False):
    pattern = "**/*.kor.png" if recursive else "*.kor.png"
    for path in sorted(directory.glob(pattern)):
        try:
            offset = int(path.name.removesuffix(".kor.png"), 16)
        except ValueError:
            continue
        yield offset, path


def write_encode_log(
    artifact_dir: Path,
    source: Path,
    format_name: str,
    entries: list[dict[str, object]],
) -> None:
    if not entries:
        return
    report = {
        "source": source.name,
        "format": format_name,
        "entries": entries,
    }
    (artifact_dir / "encode_log.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\r\n",
    )


def remove_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def encode_planar_folder(
    source: Path,
    artifact_dir: Path,
    layout: dict[int, tuple[int, int]],
    *,
    recursive: bool = False,
    all_artifacts: bool = False,
) -> int:
    if not artifact_dir.is_dir():
        return 0
    entries = []
    for offset, png_path in offset_pngs(artifact_dir, recursive=recursive):
        if offset not in layout:
            raise ValueError(f"{png_path}: offset is not a known frame boundary for {source.name}")
        width, height = layout[offset]
        planar, pixels = image_to_planar(png_path, width, height)
        stem = f"{offset:06X}"
        output_path = png_path.with_name(f"{stem}.pln.kor.bin")
        output_path.write_bytes(planar)
        files = {
            "png": png_path.relative_to(artifact_dir).as_posix(),
            "planar": output_path.relative_to(artifact_dir).as_posix(),
        }
        if all_artifacts:
            pixels_path = png_path.with_name(f"{stem}.idx.kor.bin")
            pixels_path.write_bytes(pixels)
            files["pixels"] = pixels_path.relative_to(artifact_dir).as_posix()
        else:
            remove_if_exists(png_path.with_name(f"{stem}.idx.kor.bin"))
        entries.append(
            {
                "offset": hex_offset(offset),
                "width": width,
                "height": height,
                "encoded_size": len(planar),
                "files": files,
            }
        )
        print(f"{png_path}: encoded={len(planar)}")
    write_encode_log(
        artifact_dir,
        source,
        "interleaved 3bpp B/R/G planar",
        entries,
    )
    return len(entries)


def find_pak_png(artifact_dir: Path, source: Path) -> Path | None:
    native = artifact_dir / f"{source.stem}.kor.png"
    legacy = artifact_dir / "000000.kor.png"
    candidates = [path for path in (native, legacy) if path.is_file()]
    if len(candidates) > 1:
        raise ValueError(f"{artifact_dir}: both native and legacy Korean PNG names exist")
    return candidates[0] if candidates else None


def encode_pak_file(
    source: Path,
    artifact_dir: Path,
    width: int,
    height: int,
    literal_rows: int,
    copy_rows: int,
    *,
    padding: bool = True,
    all_artifacts: bool = False,
    allow_growth: bool = False,
    png_path: Path | None = None,
    write_log: bool = True,
    log_entries: list[dict[str, object]] | None = None,
) -> int:
    if not artifact_dir.is_dir():
        return 0
    if png_path is None:
        png_path = find_pak_png(artifact_dir, source)
    if png_path is None:
        return 0
    if not png_path.is_file():
        return 0

    planar, pixels = image_to_planar(png_path, width, height)
    compressed = encode_pak(planar, width, height, literal_rows, copy_rows)
    original_size = source.stat().st_size
    exceeds_original = len(compressed) > original_size
    if padding and exceeds_original and not allow_growth:
        raise ValueError(f"{png_path}: encoded PAK {len(compressed)} exceeds original size {original_size}")
    padded = padding and not exceeds_original
    padding_size = original_size - len(compressed) if padded else 0
    encoded = compressed + bytes((DOS_PADDING,)) * padding_size
    output_name = source.name
    (artifact_dir / output_name).write_bytes(encoded)

    files = {"png": png_path.name, "encoded": output_name}
    if all_artifacts:
        planar_name = f"{source.stem}.pln.kor.bin"
        pixels_name = f"{source.stem}.idx.kor.bin"
        (artifact_dir / planar_name).write_bytes(planar)
        (artifact_dir / pixels_name).write_bytes(pixels)
        files.update({"planar": planar_name, "pixels": pixels_name})
    else:
        remove_if_exists(artifact_dir / f"{source.stem}.pln.kor.bin")
        remove_if_exists(artifact_dir / f"{source.stem}.idx.kor.bin")
    entry = {
        "offset": hex_offset(0),
        "width": width,
        "height": height,
        "original_size": original_size,
        "compressed_size": len(compressed),
        "padding_size": padding_size,
        "output_size": len(encoded),
        "padded": padded,
        "files": files,
    }
    if write_log:
        write_encode_log(
            artifact_dir,
            source,
            "Nobu2 0x96 vertical-copy PAK",
            [entry],
        )
    if log_entries is not None:
        log_entries.append({"source": source.name, **entry})
    print(f"{png_path}: compressed={len(compressed)} padding={padding_size} output={len(encoded)}")
    return 1


def odamain_layout() -> dict[int, tuple[int, int]]:
    return {ODAMAIN_TABLE_OFFSET + index * ODAMAIN_RECORD_SIZE + 2: (16, 8) for index in range(ODAMAIN_COUNT)}


# Add new encoders here explicitly. No image folder is processed implicitly.
MANUAL_PLANAR_JOBS = (("ODAMAIN.EXE", odamain_layout()),)

MANUAL_PAK_JOBS = (
    ("TITLE.PAK", PAK_SPECS["TITLE.PAK"]),
    ("END2.PAK", PAK_SPECS["END2.PAK"]),
)

MANUAL_MAP_PAK_JOBS = (
    "MAP17.PAK",
    "HOKURIKU.PAK",
    "KANTOU.PAK",
    "KINKI.PAK",
    "KYUSYU.PAK",
    "SHIKOKU.PAK",
    "TOUHOKU.PAK",
    "TYUBU.PAK",
)

# These streams fit both releases, but standalone-size padding would cross the
# following record boundary in the 384 KB MAP.DAT container.
DUAL_RELEASE_UNPADDED_MAPS = {
    "MAP17.PAK",
    "KINKI.PAK",
    "TYUBU.PAK",
}


def encode_map_paks(
    workspace: ImageWorkspace,
    *,
    padding: bool = True,
    all_artifacts: bool = False,
) -> int:
    artifact_dir = workspace.root / "binary_inputs-pc98/MAP"
    if not artifact_dir.is_dir():
        return 0

    entries: list[dict[str, object]] = []
    count = 0
    for name in MANUAL_MAP_PAK_JOBS:
        width, height, literal_rows, copy_rows = PAK_SPECS[name]
        count += encode_pak_file(
            workspace.source(name),
            artifact_dir,
            width,
            height,
            literal_rows,
            copy_rows,
            padding=padding and name not in DUAL_RELEASE_UNPADDED_MAPS,
            all_artifacts=all_artifacts,
            allow_growth=True,
            png_path=artifact_dir / f"{name}.KOR.png",
            write_log=False,
            log_entries=entries,
        )
    if entries:
        report = {
            "format": "Nobu2 0x96 vertical-copy PAK",
            "entries": entries,
        }
        (artifact_dir / "encode_log.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )
    return count


def encode_all(
    workspace: ImageWorkspace,
    *,
    padding: bool = True,
    all_artifacts: bool = False,
    link_384k: bool = True,
) -> int:
    count = 0
    binary_inputs = workspace.root / "binary_inputs-pc98"
    for name, layout in MANUAL_PLANAR_JOBS:
        count += encode_planar_folder(
            workspace.source(name),
            binary_inputs / name,
            layout,
            all_artifacts=all_artifacts,
        )
    for name, spec in MANUAL_PAK_JOBS:
        width, height, literal_rows, copy_rows = spec
        count += encode_pak_file(
            workspace.source(name),
            binary_inputs / name,
            width,
            height,
            literal_rows,
            copy_rows,
            padding=padding,
            all_artifacts=all_artifacts,
        )
    count += encode_map_paks(
        workspace,
        padding=padding,
        all_artifacts=all_artifacts,
    )
    if link_384k:
        script_384k = workspace.root / "script-pc98-384k"
        source_384k = workspace.root / "jpn-pc98-384k"
        if script_384k.is_dir() and source_384k.is_dir():
            prepare_graphics_384k(workspace.root)
        else:
            print("384 KB workspace not found; skipped binary_input linking")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("c:/work_han/workspace0"),
        help="workspace containing jpn-pc98 and binary_inputs-pc98 (default: c:/work_han/workspace0)",
    )
    parser.add_argument(
        "--compose",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="build manually configured *.kor.png files from *.bg.png first (default: enabled)",
    )
    parser.add_argument(
        "--padding",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "pad PAK output with 0x1A to its original file size; map PAKs "
            "that grow are written without padding (default: enabled)"
        ),
    )
    parser.add_argument(
        "--all-artifacts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="also write indexed pixel binaries (default: disabled)",
    )
    parser.add_argument(
        "--link-384k",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="update script-pc98-384k binary_input links after encoding (default: enabled)",
    )
    args = parser.parse_args()
    if args.compose:
        build_korean_graphics(args.workspace)
        build_map_graphics(args.workspace)
    count = encode_all(
        ImageWorkspace(args.workspace),
        padding=args.padding,
        all_artifacts=args.all_artifacts,
        link_384k=args.link_384k,
    )
    print(f"encoded {count} Korean PNG(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
