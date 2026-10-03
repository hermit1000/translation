#!/usr/bin/env python3
"""Decode Dracula PC-98 GPC images into the workspace image artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from gspecific.dob1.gpc import collect_gpc_output_modes
from module.pc98_image.adv98_artifacts import write_artifacts
from module.pc98_image.formats.adv98_gpc import (
    decode_gpc,
    decode_packed_palette_dac,
)


def decode_dracula_gpc(data: bytes, *, output_mode: int = 0):
    # The shared XOR routine matches ADVBIOS.OVL.dec 2787..27C2.
    return decode_gpc(
        data, output_mode=output_mode,
        palette_decoder=decode_packed_palette_dac,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(r"C:\work_han\workspace2"))
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        help="GPC filename; may be repeated (default: all GPC files)",
    )
    parser.add_argument(
        "--mode",
        type=int,
        choices=(0, 1),
        help="force one GPC output mode instead of inferring it from MES usage",
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_root = workspace / "jpn-pc98" / "GPC"
    sources = sorted(source_root.glob("*.GPC"))
    if args.files:
        wanted = {name.upper() for name in args.files}
        sources = [source for source in sources if source.name.upper() in wanted]
    if not sources:
        raise FileNotFoundError(f"no requested GPC files found under {source_root}")

    observed = collect_gpc_output_modes(workspace / "jpn-pc98" / "MES")
    for source in sources:
        modes = observed.get(source.name.upper(), Counter())
        output_mode = args.mode
        if output_mode is None:
            output_mode = modes.most_common(1)[0][0] if modes else 1
        output = workspace / "image-pc98" / "GPC" / source.name
        decoded = write_artifacts(
            source,
            output,
            output_mode=output_mode,
            observed_modes=dict(modes),
            decoder=decode_dracula_gpc,
            png_output=workspace / "image-pc98" / "png",
        )
        print(
            f"{source.name}: {decoded.width}x{decoded.height}, "
            f"mode={decoded.output_mode}, compressed={decoded.compressed_size}, "
            f"output={output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
