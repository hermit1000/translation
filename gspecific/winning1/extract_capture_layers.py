#!/usr/bin/env python3
"""Split the BGSET monochrome capture into reusable transparent layers."""

from pathlib import Path

from PIL import Image


def extract_layer(image: Image.Image, box: tuple[int, int, int, int], output: Path) -> None:
    layer = image.crop(box).convert("RGBA")
    layer.putalpha(layer.convert("RGB").getchannel("R"))
    output.parent.mkdir(parents=True, exist_ok=True)
    layer.save(output)


def main() -> None:
    capture = Path("c:/work_han/workspace3/capture/bgset_000.raw1.png")
    image = Image.open(capture)
    extract_layer(image, (134, 141, 507, 210), capture.with_name("bgset_000.raw1.title.png"))
    extract_layer(image, (136, 226, 502, 246), capture.with_name("bgset_000.raw1.production.png"))


if __name__ == "__main__":
    main()
