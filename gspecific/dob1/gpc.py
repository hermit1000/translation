"""DOB1 GPC command line and compatibility exports for the shared codec."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from module.pc98_image.adv98_artifacts import write_artifacts
from module.pc98_image.formats.adv98_gpc import (
    SIGNATURE, HEADER_SIZE, DESCRIPTOR_SIZE, PLANES, GPCImage,
    u16, u32, decode_packed_palette, decode_packed_palette_dac,
    unpack_zero_masks, pack_zero_masks, undo_xor_delta, undo_xor_delta_runtime,
    planar_rows_to_indices, apply_output_mode, decode_gpc, encode_gpc,
)


def collect_gpc_output_modes(mes_root: Path) -> dict[str, Counter[int]]:
    """Collect C9/CF file and output-mode pairs from lexical MES decoding."""
    from gspecific.dob1.adv98_mes.decode_mes import decode_mes

    usage: defaultdict[str, Counter[int]] = defaultdict(Counter)
    for path in sorted(mes_root.glob("*.MES")):
        data = path.read_bytes()
        current_name = None
        for token in decode_mes(data):
            if token.get("type") != "command":
                continue
            opcode = token["bytes"][0]
            offset = token["offset"]
            if opcode == 0xC9 and offset + 1 < len(data) and data[offset + 1] == 0x22:
                end = data.find(b'"', offset + 2)
                if end >= 0:
                    value = data[offset + 2 : end].decode("ascii", errors="replace")
                    current_name = value.replace("\\", "/").rsplit("/", 1)[-1].upper()
            elif opcode == 0xCF and current_name and offset + 1 < len(data):
                encoded_mode = data[offset + 1]
                if 0x23 <= encoded_mode <= 0x27:
                    usage[current_name][encoded_mode - 0x23] += 1
    return dict(usage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        help="GRAPH-relative GPC name; may be repeated (default: all GPC files)",
    )
    parser.add_argument(
        "--mode",
        type=int,
        choices=(0, 1),
        help="force one GPC output mode instead of inferring it from MES usage",
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_root = workspace / "jpn-pc98" / "GRAPH"
    names = args.files or [path.name for path in sorted(source_root.glob("*.GPC"))]
    if not names:
        raise FileNotFoundError(f"no GPC files found under {source_root}")

    observed = collect_gpc_output_modes(workspace / "jpn-pc98" / "MES")

    for name in names:
        source = source_root / name
        if not source.is_file():
            raise FileNotFoundError(source)
        output = workspace / "image-pc98" / "GRAPH" / source.name
        modes = observed.get(source.name.upper(), Counter())
        output_mode = args.mode
        if output_mode is None:
            output_mode = modes.most_common(1)[0][0] if modes else 1
        decoded = write_artifacts(
            source,
            output,
            output_mode=output_mode,
            observed_modes=dict(modes),
        )
        print(
            f"{source.name}: {decoded.width}x{decoded.height}, "
            f"mode={decoded.output_mode}, compressed={decoded.compressed_size}, "
            f"output={output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
