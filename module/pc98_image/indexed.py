"""Palette-indexed image data independent of Pillow and file formats."""

from dataclasses import dataclass
from typing import Sequence

Color = tuple[int, int, int]


@dataclass(frozen=True)
class IndexedImage:
    width: int
    height: int
    indices: bytes
    palette: tuple[Color, ...] | None = None

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("image dimensions must be positive")
        if len(self.indices) != self.width * self.height:
            raise ValueError(
                f"index size mismatch: got {len(self.indices)}, "
                f"expected {self.width * self.height}"
            )
        if self.palette is not None:
            if not self.palette:
                raise ValueError("palette must not be empty")
            if any(index >= len(self.palette) for index in self.indices):
                raise ValueError("pixel index is outside the palette")

    @classmethod
    def create(
        cls,
        width: int,
        height: int,
        indices: bytes | bytearray,
        palette: Sequence[Color] | None = None,
    ) -> "IndexedImage":
        normalized_palette = tuple(palette) if palette is not None else None
        return cls(width, height, bytes(indices), normalized_palette)
