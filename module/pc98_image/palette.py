"""Palette parsing and color matching primitives."""

from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Iterable, Sequence

Color = tuple[int, int, int]

PC98_PALETTE_3BPP: tuple[Color, ...] = (
    (0x00, 0x00, 0x00),
    (0x00, 0x00, 0xFF),
    (0xFF, 0x00, 0x00),
    (0xFF, 0x00, 0xFF),
    (0x00, 0xFF, 0x00),
    (0x00, 0xFF, 0xFF),
    (0xFF, 0xFF, 0x00),
    (0xFF, 0xFF, 0xFF),
)

PC98_PALETTE_4BPP: tuple[Color, ...] = tuple(
    (
        (0xAA if index & 2 else 0) + (0x55 if index & 8 else 0),
        (0xAA if index & 4 else 0) + (0x55 if index & 8 else 0),
        (0xAA if index & 1 else 0) + (0x55 if index & 8 else 0),
    )
    for index in range(16)
)


def decode_4bit_palette(
    data: bytes | bytearray,
    *,
    order: str = "rgb",
) -> tuple[Color, ...]:
    """Decode three-byte RGB-component entries whose values are in 0..15."""
    if sorted(order) != ["b", "g", "r"] or len(order) != 3:
        raise ValueError("order must be a permutation of 'rgb'")
    if len(data) % 3:
        raise ValueError("palette data size must be divisible by 3")

    colors = []
    for offset in range(0, len(data), 3):
        components = dict(zip(order, data[offset : offset + 3]))
        if any(value > 0x0F for value in components.values()):
            raise ValueError("4-bit palette component exceeds 15")
        colors.append(
            (
                components["r"] * 17,
                components["g"] * 17,
                components["b"] * 17,
            )
        )
    return tuple(colors)


def encode_4bit_palette(
    colors: Iterable[Color],
    *,
    order: str = "rgb",
) -> bytes:
    """Encode exact 17-step RGB colors as three 4-bit components."""
    if sorted(order) != ["b", "g", "r"] or len(order) != 3:
        raise ValueError("order must be a permutation of 'rgb'")

    output = bytearray()
    for color in colors:
        if len(color) != 3 or any(value < 0 or value > 255 or value % 17 for value in color):
            raise ValueError("palette colors must contain RGB values in 17-step increments")
        components = dict(zip("rgb", (value // 17 for value in color)))
        output.extend(components[channel] for channel in order)
    return bytes(output)


def nearest_palette_index(
    rgb: Sequence[int],
    palette: Sequence[Color],
    *,
    prefer_last: bool = False,
) -> int:
    if not palette:
        raise ValueError("palette must not be empty")
    red, green, blue = rgb[:3]
    distances = [
        (red - pr) ** 2 + (green - pg) ** 2 + (blue - pb) ** 2
        for pr, pg, pb in palette
    ]
    best = min(distances)
    candidates = [index for index, distance in enumerate(distances) if distance == best]
    return candidates[-1] if prefer_last else candidates[0]


def exact_palette_index(rgb: Sequence[int], palette: Sequence[Color]) -> int:
    color = tuple(rgb[:3])
    try:
        return palette.index(color)
    except ValueError as error:
        raise ValueError(f"color {color} is not in the palette") from error


def check_duplicated_elements(colors: Sequence[Color]) -> tuple[bool, list[Color]]:
    """Create distinct display colors while preserving palette index positions."""
    palette = deepcopy(list(colors))
    changed = False
    while duplicates := [color for color, count in Counter(palette).items() if count > 1]:
        changed = True
        for duplicate in duplicates:
            index = palette.index(duplicate)
            replacement = None
            for delta in range(1, 256):
                for channel in range(3):
                    for direction in (-1, 1):
                        value = duplicate[channel] + direction * delta
                        if not 0 <= value <= 255:
                            continue
                        candidate = list(duplicate)
                        candidate[channel] = value
                        if tuple(candidate) not in palette:
                            replacement = tuple(candidate)
                            break
                    if replacement is not None:
                        break
                if replacement is not None:
                    break
            if replacement is None:
                raise ValueError("could not create a distinct pseudo-palette color")
            palette[index] = replacement
    return changed, palette


def match_color(rgb: Sequence[int], palette: Sequence[Color]) -> int:
    return exact_palette_index(rgb, palette)


def find_closest_color_index(
    rgb: Sequence[int],
    palette: Sequence[Color],
    tie_breaking_rule: str = "first",
) -> int:
    if tie_breaking_rule not in {"first", "last"}:
        raise ValueError(f"unknown tie-breaking rule: {tie_breaking_rule}")
    return nearest_palette_index(
        rgb,
        palette,
        prefer_last=tie_breaking_rule == "last",
    )


class Palettes:
    """Compatibility container for files containing 16-color palettes."""

    def __init__(self, palette_file_path: str = "", order: str = "rgb") -> None:
        self.palettes: list[list[Color]] = []
        if palette_file_path:
            self.set_palettes(Path(palette_file_path).read_bytes(), order)

    def color(self, index: int) -> Color:
        return self.palettes[0][index]

    def set_palettes(self, data: bytes | bytearray, order: str = "rgb") -> None:
        if len(data) % 48:
            raise ValueError("palette data size must be a multiple of 48")
        self.palettes = [
            list(decode_4bit_palette(data[offset : offset + 48], order=order))
            for offset in range(0, len(data), 48)
        ]
