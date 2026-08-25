"""Stage 1: rebuild editable backgrounds used by the Korean image stage."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image


TARGETS = [
    ((238, 88, 374, 105), {11}),
    ((296, 200, 459, 265), {12, 13}),
]
PROTECTED = [(438, 200, 459, 216)]


def flood_components(
    image: Image.Image,
    box: tuple[int, int, int, int],
    colors: set[int],
) -> set[tuple[int, int]]:
    left, top, right, bottom = box
    pixels = image.load()
    seeds = {
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if pixels[x, y] in colors
    }
    selected: set[tuple[int, int]] = set()
    while seeds:
        seed = seeds.pop()
        color = pixels[seed]
        queue = deque([seed])
        component = {seed}
        while queue:
            x, y = queue.popleft()
            for ny in range(max(top, y - 1), min(bottom, y + 2)):
                for nx in range(max(left, x - 1), min(right, x + 2)):
                    point = (nx, ny)
                    if point not in component and pixels[point] == color:
                        component.add(point)
                        queue.append(point)
        selected.update(component)
        seeds.difference_update(component)
    return selected


def build_mask(root: Path) -> Path:
    source = Image.open(root / "BLTY_AB.jpn.png")
    if source.mode != "P":
        raise ValueError(f"expected indexed BLTY source, got {source.mode}")
    selected: set[tuple[int, int]] = set()
    for box, colors in TARGETS:
        selected.update(flood_components(source, box, colors))
    for left, top, right, bottom in PROTECTED:
        selected.difference_update(
            (x, y) for y in range(top, bottom) for x in range(left, right)
        )

    mask = Image.new("L", source.size, 0)
    mask_pixels = mask.load()
    for point in selected:
        mask_pixels[point] = 255
    mask_path = root / "BLTY_AB.remove-mask.png"
    mask.save(mask_path)

    review = source.convert("RGB")
    review_pixels = review.load()
    for point in selected:
        review_pixels[point] = (255, 255, 0)
    review.save(root / "BLTY_AB.jpn.test.png")
    print(f"selected mask pixels: {len(selected)}")
    print(f"wrote: {mask_path}")
    return mask_path


def nearest_index(
    rgb: tuple[int, int, int], colors: list[tuple[int, int, int]]
) -> int:
    r, g, b = rgb
    return min(
        range(len(colors)),
        key=lambda i: sum(
            (value - colors[i][channel]) ** 2
            for channel, value in enumerate((r, g, b))
        ),
    )


def build_blty_background(root: Path, mask_path: Path) -> Path:
    source = Image.open(root / "BLTY_AB.jpn.png")
    mask = Image.open(mask_path).convert("L")
    generated = Image.open(root / "BLTY_AB.bg.imagegen.png").convert("RGB")
    generated = generated.resize(source.size, Image.Resampling.NEAREST)

    palette = source.getpalette()
    colors = [tuple(palette[i:i + 3]) for i in range(0, 48, 3)]
    result = source.copy()
    source_pixels = source.load()
    result_pixels = result.load()
    mask_pixels = mask.load()
    generated_pixels = generated.load()
    for y in range(source.height):
        for x in range(source.width):
            if mask_pixels[x, y]:
                result_pixels[x, y] = nearest_index(generated_pixels[x, y], colors)

    assert all(
        mask_pixels[x, y] or result_pixels[x, y] == source_pixels[x, y]
        for y in range(source.height)
        for x in range(source.width)
    )
    output = root / "BLTY_AB.bg.png"
    result.save(output)
    print(f"wrote: {output}")
    print("unmasked index differences: 0")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args()
    root = args.workspace.resolve() / "binary_inputs-pc98"

    frr = root / "FRR.bg.png"
    if not frr.is_file():
        raise FileNotFoundError(f"prepared FRR background is missing: {frr}")
    print(f"using prepared FRR background: {frr}")

    generated = root / "BLTY_AB.bg.imagegen.png"
    prepared = root / "BLTY_AB.bg.png"
    if generated.is_file():
        build_blty_background(root, build_mask(root))
    elif prepared.is_file():
        print(f"using prepared BLTY background: {prepared}")
    else:
        raise FileNotFoundError(
            f"BLTY background requires {prepared} or restoration input {generated}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
