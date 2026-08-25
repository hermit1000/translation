#!/usr/bin/env python3
"""Decode every MGX found below jpn-pc98 into the image directory."""

from __future__ import annotations

import json
from pathlib import Path

from rusty_images import decode_mag_dos, decode_mag_pc98, decode_mgx, read_mgx_header


ROOT = Path(r"C:\work_han\workspace1")
PLATFORM = "dos"
INPUT_DIR = ROOT / f"jpn-{PLATFORM}"
OUTPUT_DIR = ROOT / f"image-{PLATFORM}"
MAG_DECODERS = {
    "pc98": decode_mag_pc98,
    "dos": decode_mag_dos,
}


def main() -> None:
    decode_mag = MAG_DECODERS[PLATFORM]
    files = (
        sorted(INPUT_DIR.rglob("*.MGX"))
        + sorted(INPUT_DIR.rglob("*.mgx"))
        + sorted(INPUT_DIR.rglob("*.MAG"))
        + sorted(INPUT_DIR.rglob("*.mag"))
    )
    # Avoid duplicates on case-insensitive filesystems.
    files = list(dict.fromkeys(path.resolve() for path in files))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []

    for source in files:
        relative = source.relative_to(INPUT_DIR)
        # Keep the source extension visible: R_A11.MGX -> R_A11.MGX.png.
        target = OUTPUT_DIR / (str(relative) + ".png")
        item = {"source": str(relative), "output": str(target.relative_to(OUTPUT_DIR))}
        try:
            if source.suffix.lower() == ".mag":
                item.update(status="ok", **decode_mag(source, target))
                print(f"OK   {relative} -> {target.relative_to(OUTPUT_DIR)}")
            else:
                header = read_mgx_header(source.read_bytes())
                if header["x1"] <= header["x0"] or header["y1"] <= header["y0"]:
                    item.update(status="skipped", reason="palette/control MGX")
                    print(f"SKIP {relative}")
                else:
                    item.update(status="ok", **decode_mgx(source, target))
                    print(f"OK   {relative} -> {target.relative_to(OUTPUT_DIR)}")
        except Exception as exc:
            item.update(status="error", error=str(exc))
            print(f"FAIL {relative}: {exc}")
        manifest.append(item)

    manifest_path = OUTPUT_DIR / "mgx_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(item["status"] == "ok" for item in manifest)
    skipped = sum(item["status"] == "skipped" for item in manifest)
    failed = sum(item["status"] == "error" for item in manifest)
    print(f"Converted {ok}/{len(files)}; skipped {skipped}; failed {failed}")
    print(f"Manifest: {manifest_path}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
