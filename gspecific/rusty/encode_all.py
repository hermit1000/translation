#!/usr/bin/env python3
"""Encode every ``*.MAG.png``/``*.MGX.png`` below binary_inputs-pc98.

The final ``.png`` suffix is removed, so ``STAFF1.MGX.png`` becomes
``STAFF1.MGX`` in the same relative directory.
"""

from pathlib import Path

from rusty_images import encode_mag, encode_mgx


ROOT = Path(r"C:\work_han\workspace1")
INPUT_DIR = ROOT / "binary_inputs-pc98"
MGX_COORDS = {
    "R_A23.MGX": (19, 128),
    "R_A31.MGX": (32, 132),
    "R_A36.MGX": (40, 136),
    "STAFF1.MGX": (136, 189),
    "STAFF2.MGX": (152, 144),
    "STAFF3.MGX": (152, 152),
    "STAFF4.MGX": (144, 144),
    "STAFF5.MGX": (136, 176),
    "STAFF6.MGX": (152, 188),
    "STAFF7.MGX": (216, 164),
}


def main() -> None:
    files = sorted(INPUT_DIR.rglob("*.png"))
    encoded = 0
    skipped = 0
    for source in files:
        suffix = source.name[:-4].rsplit(".", 1)[-1].lower()
        target = source.with_suffix("")
        if suffix == "mag":
            encode_mag(source, target)
        elif suffix == "mgx":
            encode_mgx(source, target, *MGX_COORDS.get(target.name, (0, 0)))
        else:
            skipped += 1
            print(f"SKIP {source.relative_to(INPUT_DIR)} (unknown original extension)")
            continue
        encoded += 1
        print(f"OK   {source.relative_to(INPUT_DIR)} -> {target.relative_to(INPUT_DIR)}")
    print(f"Encoded {encoded} file(s); skipped {skipped}.")


if __name__ == "__main__":
    main()
