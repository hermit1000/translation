#!/usr/bin/env python3
"""Encode Rusty image PNGs below the PC-98 and DOS binary input folders.

The final ``.png`` suffix is removed, so ``STAFF1.MGX.png`` becomes
``STAFF1.MGX`` and ``STAFF1.MAG.png`` becomes ``STAFF1.MAG`` in the same
relative directory.
"""

from pathlib import Path

from PIL import Image

from rusty_images import encode_mag_dos, encode_mag_pc98, encode_mgx


ROOT = Path(r"C:\work_han\workspace1")
PC98_INPUT_DIR = ROOT / "binary_inputs-pc98"
DOS_INPUT_DIR = ROOT / "binary_inputs-dos"
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
# Original DOS MAG placement and decoded size: (x, y, width, height).
DOS_MAG_INFO = {
    "GIRL5A.MAG": (0, 0, 640, 400),
    "R_A23.MAG": (16, 128, 616, 144),
    "R_A31.MAG": (32, 132, 576, 132),
    "R_A36.MAG": (40, 136, 560, 130),
    "STAFF1.MAG": (136, 189, 368, 23),
    "STAFF2.MAG": (152, 144, 336, 112),
    "STAFF3.MAG": (152, 152, 336, 102),
    "STAFF4.MAG": (144, 144, 288, 112),
    "STAFF5.MAG": (136, 176, 368, 50),
    "STAFF6.MAG": (152, 188, 336, 24),
    "STAFF7.MAG": (216, 164, 216, 68),
}


def encode_directory(
    input_dir: Path,
    *,
    allow_mgx: bool,
    mag_encoder,
    mag_info: dict[str, tuple[int, int, int, int]] | None = None,
) -> tuple[int, int]:
    files = sorted(input_dir.rglob("*.png"))
    encoded = 0
    skipped = 0
    for source in files:
        suffix = source.name[:-4].rsplit(".", 1)[-1].lower()
        target = source.with_suffix("")
        if suffix == "mag":
            if mag_info is None:
                mag_encoder(source, target)
            else:
                relative_target = str(target.relative_to(input_dir))
                info = mag_info.get(relative_target)
                if info is None:
                    raise ValueError(f"Missing DOS MAG information: {relative_target}")
                x, y, width, height = info
                with Image.open(source) as image:
                    actual_size = image.size
                expected_size = (width, height)
                if actual_size != expected_size:
                    raise ValueError(
                        f"DOS MAG size mismatch for {relative_target}: "
                        f"{actual_size} != {expected_size}"
                    )
                mag_encoder(source, target, x, y)
        elif suffix == "mgx" and allow_mgx:
            encode_mgx(source, target, *MGX_COORDS.get(target.name, (0, 0)))
        else:
            skipped += 1
            print(f"SKIP {source.relative_to(input_dir)} (unknown original extension)")
            continue
        encoded += 1
        print(f"OK   {source.relative_to(input_dir)} -> {target.relative_to(input_dir)}")
    return encoded, skipped


def main() -> None:
    print(f"[{PC98_INPUT_DIR.name}]")
    encoded, skipped = encode_directory(
        PC98_INPUT_DIR,
        allow_mgx=True,
        mag_encoder=encode_mag_pc98,
    )
    print(f"Encoded {encoded} file(s); skipped {skipped}.")

    print(f"[{DOS_INPUT_DIR.name}]")
    encoded, skipped = encode_directory(
        DOS_INPUT_DIR,
        allow_mgx=False,
        mag_encoder=encode_mag_dos,
        mag_info=DOS_MAG_INFO,
    )
    print(f"Encoded {encoded} file(s); skipped {skipped}.")


if __name__ == "__main__":
    main()
