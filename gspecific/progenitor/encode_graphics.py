#!/usr/bin/env python3
"""Encode manually configured Progenitor PC-98 Korean graphics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


FOREGROUND_RGBA = (255, 239, 223, 255)
NAME_BMD_WIDTH = 64
NAME_BMD_HEIGHT = 24
NAME_BMD_PLANES = 3
NAME_BMD_RECORD_SIZE = NAME_BMD_WIDTH * NAME_BMD_HEIGHT * NAME_BMD_PLANES // 8
PC98_MONOCHROME_MASK_RGBA = (
    (0x00, 0x00, 0x00, 0xFF),
    (0xFF, 0xFF, 0xFF, 0xFF),
)
PC98_PALETTE_8_RGBA = (
    (0x00, 0x00, 0x00, 0xFF),
    (0x00, 0x00, 0xFF, 0xFF),
    (0xFF, 0x00, 0x00, 0xFF),
    (0xFF, 0x00, 0xFF, 0xFF),
    (0x00, 0xFF, 0x00, 0xFF),
    (0x00, 0xFF, 0xFF, 0xFF),
    (0xFF, 0xFF, 0x00, 0xFF),
    (0xFF, 0xFF, 0xFF, 0xFF),
)

# Add new encoders here explicitly. No PNG is processed implicitly.
MANUAL_MASK_JOBS = (
    ("OPEN.NPK/000e10.kor.png", 272, 48),
)

PROGENITOR_LOGO_PALETTE_RGBA = (
    (0x00, 0x00, 0x00, 0x00),
    (0x22, 0x33, 0x66, 0xFF),
    (0xFF, 0x00, 0x00, 0xFF),
    (0xCC, 0x55, 0x88, 0xFF),
    (0x44, 0x88, 0x00, 0xFF),
    (0x99, 0xBB, 0xCC, 0xFF),
    (0xFF, 0xAA, 0x66, 0xFF),
    (0xFF, 0xEE, 0xDD, 0xFF),
    (0x00, 0x00, 0x00, 0xFF),
    (0x22, 0x55, 0xAA, 0xFF),
    (0x88, 0x22, 0x00, 0xFF),
    (0xDD, 0x55, 0x22, 0xFF),
    (0x11, 0x55, 0x00, 0xFF),
    (0x55, 0x77, 0xCC, 0xFF),
    (0xBB, 0x77, 0x22, 0xFF),
    (0xFF, 0xFF, 0xFF, 0xFF),
)

MANUAL_4BPP_JOBS = (
    ("OPEN.NPK/004941.kor.png", 400, 144, PROGENITOR_LOGO_PALETTE_RGBA),
)
PUT_IMAGE_SPECS = {
    **{index * 0x20: (16, 16, 1, "digit-font-16x16") for index in range(10)},
    **{0x140 + index * 0x10: (8, 16, 1, "digit-font-8x16") for index in range(10)},
    **{0x1F0 + index * 0x0A: (8, 10, 1, "digit-font-8x10") for index in range(10)},
    **{
        start + index * 0x60: (16, 16, 3, "ui-part-16x16")
        for start in (0x254, 0x2BF4)
        for index in range(5)
    },
    **{0x2DD4 + index * 0x18: (8, 8, 3, "window-tile-8x8") for index in range(15)},
    **{0x66BC + index * 0xD8: (24, 24, 3, "battle-ui-icon-24x24") for index in range(12)},
}


def normalize_path(path: Path) -> Path:
    path_text = str(path)
    if len(path_text) >= 3 and path_text[1:3] == ":/":
        drive = path_text[0].lower()
        return Path("/mnt") / drive / path_text[3:]
    return path


def image_to_mask(
    png_path: Path,
    width: int,
    height: int,
) -> tuple[bytes, bytes]:
    with Image.open(png_path) as source:
        image = source.convert("RGBA")

    if image.size != (width, height):
        raise ValueError(
            f"{png_path}: image size is {image.width}x{image.height}, "
            f"expected {width}x{height}"
        )
    if width % 8:
        raise ValueError(f"{png_path}: 1bpp image width must be divisible by 8")

    planar = bytearray(width * height // 8)
    indices = bytearray(width * height)
    for position, pixel in enumerate(image.getdata()):
        if pixel[3] == 0:
            continue
        if pixel != FOREGROUND_RGBA:
            raise ValueError(
                f"{png_path}: unsupported RGBA color {pixel} at "
                f"({position % width}, {position // width})"
            )
        planar[position // 8] |= 0x80 >> (position % 8)
        indices[position] = 7
    return bytes(planar), bytes(indices)


def image_to_row_plane_major(
    png_path: Path,
    width: int,
    height: int,
    planes: int,
    palette: tuple[tuple[int, int, int, int], ...],
) -> tuple[bytes, bytes]:
    with Image.open(png_path) as source:
        image = source.convert("RGBA")

    if image.size != (width, height):
        raise ValueError(
            f"{png_path}: image size is {image.width}x{image.height}, "
            f"expected {width}x{height}"
        )
    if width % 8:
        raise ValueError(f"{png_path}: planar image width must be divisible by 8")
    if len(palette) != 1 << planes or len(set(palette)) != len(palette):
        raise ValueError(f"{planes}bpp RGBA palette must contain {1 << planes} distinct colors")

    color_to_index = {color: index for index, color in enumerate(palette)}
    indices = bytearray(width * height)
    for position, pixel in enumerate(image.getdata()):
        if pixel not in color_to_index and pixel[3] == 0:
            pixel = palette[0]
        try:
            indices[position] = color_to_index[pixel]
        except KeyError as error:
            raise ValueError(
                f"{png_path}: unsupported RGBA color {pixel} at "
                f"({position % width}, {position // width})"
            ) from error

    stride = width // 8
    planar = bytearray(stride * height * planes)
    for y in range(height):
        row_offset = y * stride * planes
        for plane in range(planes):
            plane_offset = row_offset + plane * stride
            for x_byte in range(stride):
                value = 0
                pixel_offset = y * width + x_byte * 8
                for bit in range(8):
                    if indices[pixel_offset + bit] & (1 << plane):
                        value |= 0x80 >> bit
                planar[plane_offset + x_byte] = value

    return bytes(planar), bytes(indices)


def image_to_row_plane_major_4bpp(
    png_path: Path,
    width: int,
    height: int,
    palette: tuple[tuple[int, int, int, int], ...],
) -> tuple[bytes, bytes]:
    return image_to_row_plane_major(png_path, width, height, 4, palette)


def encode_name_bmd(binary_inputs: Path, reports: dict[Path, list[dict[str, object]]], all_artifacts: bool) -> int:
    directory = binary_inputs / "NAME.BMD"
    if not directory.is_dir():
        return 0

    count = 0
    for png_path in sorted(directory.glob("*.kor.png")):
        if png_path.name == "contact_sheet.kor.png":
            continue

        stem = png_path.name.removesuffix(".kor.png")
        offset = int(stem, 16)
        planar, indices = image_to_row_plane_major(
            png_path,
            NAME_BMD_WIDTH,
            NAME_BMD_HEIGHT,
            NAME_BMD_PLANES,
            PC98_PALETTE_8_RGBA,
        )
        if len(planar) != NAME_BMD_RECORD_SIZE:
            raise ValueError(f"{png_path}: encoded size is {len(planar)}, expected {NAME_BMD_RECORD_SIZE}")

        planar_path = png_path.with_name(f"{stem}.pln.kor.bin")
        planar_path.write_bytes(planar)

        files = {
            "png": png_path.name,
            "planar": planar_path.name,
        }
        indices_path = png_path.with_name(f"{stem}.idx.kor.bin")
        if all_artifacts:
            indices_path.write_bytes(indices)
            files["pixels"] = indices_path.name
        else:
            indices_path.unlink(missing_ok=True)

        reports.setdefault(directory, []).append(
            {
                "offset": f"0x{offset:06X}",
                "width": NAME_BMD_WIDTH,
                "height": NAME_BMD_HEIGHT,
                "planes": NAME_BMD_PLANES,
                "plane_order": "BRG",
                "planar_layout": "row-plane-major",
                "stride": NAME_BMD_WIDTH // 8,
                "record_size": NAME_BMD_RECORD_SIZE,
                "encoded_size": len(planar),
                "palette_rgba": [list(color) for color in PC98_PALETTE_8_RGBA],
                "files": files,
            }
        )
        print(f"{png_path}: encoded={len(planar)}")
        count += 1

    return count


def encode_put_dat(binary_inputs: Path, reports: dict[Path, list[dict[str, object]]], all_artifacts: bool) -> int:
    directory = binary_inputs / "PUT.DAT"
    if not directory.is_dir():
        return 0

    count = 0
    for png_path in sorted(directory.glob("*.kor.png")):
        stem = png_path.name.removesuffix(".kor.png")
        offset = int(stem, 16)
        try:
            width, height, planes, category = PUT_IMAGE_SPECS[offset]
        except KeyError as error:
            raise ValueError(f"{png_path}: no PUT.DAT encoding spec for offset 0x{offset:06X}") from error

        palette = PC98_PALETTE_8_RGBA if planes == 3 else PC98_MONOCHROME_MASK_RGBA
        planar, indices = image_to_row_plane_major(
            png_path,
            width,
            height,
            planes,
            palette,
        )
        encoded_size = width * height * planes // 8
        if len(planar) != encoded_size:
            raise ValueError(f"{png_path}: encoded size is {len(planar)}, expected {encoded_size}")

        planar_path = png_path.with_name(f"{stem}.pln.kor.bin")
        planar_path.write_bytes(planar)

        files = {
            "png": png_path.name,
            "planar": planar_path.name,
        }
        indices_path = png_path.with_name(f"{stem}.idx.kor.bin")
        if all_artifacts:
            indices_path.write_bytes(indices)
            files["pixels"] = indices_path.name
        else:
            indices_path.unlink(missing_ok=True)

        reports.setdefault(directory, []).append(
            {
                "offset": f"0x{offset:06X}",
                "width": width,
                "height": height,
                "planes": planes,
                "plane_order": "BRG" if planes == 3 else "mask",
                "planar_layout": "row-plane-major",
                "stride": width // 8,
                "category": category,
                "encoded_size": len(planar),
                "palette_rgba": [list(color) for color in palette],
                "files": files,
            }
        )
        print(f"{png_path}: encoded={len(planar)}")
        count += 1

    return count


def encode_all(workspace: Path, *, all_artifacts: bool = False) -> int:
    binary_inputs = workspace / "binary_inputs-pc98"
    reports: dict[Path, list[dict[str, object]]] = {}
    count = 0

    for relative_png, width, height in MANUAL_MASK_JOBS:
        png_path = binary_inputs / relative_png
        if not png_path.is_file():
            raise FileNotFoundError(f"configured Korean PNG not found: {png_path}")

        planar, indices = image_to_mask(png_path, width, height)
        stem = png_path.name.removesuffix(".kor.png")
        planar_path = png_path.with_name(f"{stem}.pln.kor.bin")
        planar_path.write_bytes(planar)

        files = {
            "png": png_path.name,
            "planar": planar_path.name,
        }
        indices_path = png_path.with_name(f"{stem}.idx.kor.bin")
        if all_artifacts:
            indices_path.write_bytes(indices)
            files["pixels"] = indices_path.name
        else:
            indices_path.unlink(missing_ok=True)

        reports.setdefault(png_path.parent, []).append(
            {
                "offset": f"0x{int(stem, 16):06X}",
                "width": width,
                "height": height,
                "planes": 1,
                "planar_layout": "row-major",
                "encoded_size": len(planar),
                "files": files,
            }
        )
        print(f"{png_path}: encoded={len(planar)}")
        count += 1

    for relative_png, width, height, palette in MANUAL_4BPP_JOBS:
        png_path = binary_inputs / relative_png
        if not png_path.is_file():
            raise FileNotFoundError(f"configured Korean PNG not found: {png_path}")

        planar, indices = image_to_row_plane_major_4bpp(
            png_path,
            width,
            height,
            palette,
        )
        stem = png_path.name.removesuffix(".kor.png")
        planar_path = png_path.with_name(f"{stem}.pln.kor.bin")
        planar_path.write_bytes(planar)

        files = {
            "png": png_path.name,
            "planar": planar_path.name,
        }
        indices_path = png_path.with_name(f"{stem}.idx.kor.bin")
        if all_artifacts:
            indices_path.write_bytes(indices)
            files["pixels"] = indices_path.name
        else:
            indices_path.unlink(missing_ok=True)

        reports.setdefault(png_path.parent, []).append(
            {
                "offset": f"0x{int(stem, 16):06X}",
                "width": width,
                "height": height,
                "planes": 4,
                "plane_order": "BRGI",
                "planar_layout": "row-plane-major",
                "encoded_size": len(planar),
                "palette_rgba": [list(color) for color in palette],
                "files": files,
            }
        )
        print(f"{png_path}: encoded={len(planar)}")
        count += 1

    count += encode_name_bmd(binary_inputs, reports, all_artifacts)
    count += encode_put_dat(binary_inputs, reports, all_artifacts)

    for directory, entries in reports.items():
        report = {
            "format": "raw planar graphics, MSB first",
            "foreground_rgba": list(FOREGROUND_RGBA),
            "entries": entries,
        }
        (directory / "encode_log.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("c:/work_han/workspace1"),
        help=(
            "workspace containing binary_inputs-pc98 "
            "(default: c:/work_han/workspace1)"
        ),
    )
    parser.add_argument(
        "--all-artifacts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="also write indexed pixel binaries (default: no-all-artifacts)",
    )
    args = parser.parse_args()
    count = encode_all(
        normalize_path(args.workspace).resolve(),
        all_artifacts=args.all_artifacts,
    )
    print(f"encoded {count} Korean PNG(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
