"""Decode Marine Philt PC-98 GPC images into one artifact directory."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from gspecific.dob1.gpc import write_artifacts
from gspecific.marine_philt.adv98_mes.decode_mes import decode_mes


def collect_output_modes(mes_root: Path) -> dict[str, Counter[int]]:
    usage: defaultdict[str, Counter[int]] = defaultdict(Counter)
    for path in sorted(mes_root.glob("*.MES")):
        tokens = decode_mes(path.read_bytes())
        current_name: str | None = None
        for index, token in enumerate(tokens):
            if token.get("type") != "command":
                continue
            opcode = token["bytes"][0]
            if opcode == 0xC9:
                for following in tokens[index + 1 : index + 3]:
                    if following.get("type") == "quoted":
                        current_name = (
                            str(following["value"])
                            .replace("\\", "/")
                            .rsplit("/", 1)[-1]
                            .upper()
                        )
                        break
            elif opcode == 0xCF and current_name:
                if index + 1 < len(tokens) and tokens[index + 1].get("type") == "argument":
                    mode = tokens[index + 1]["value"]
                    if mode in (0, 1):
                        usage[current_name][mode] += 1
    return dict(usage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        help="GRAPH-relative GPC filename; may be repeated (default: all)",
    )
    parser.add_argument("--mode", type=int, choices=(0, 1))
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_root = workspace / "jpn-pc98" / "GRAPH"
    output = workspace / "image-pc98" / "GPC"
    names = args.files or [path.name for path in sorted(source_root.glob("*.GPC"))]
    if not names:
        raise FileNotFoundError(f"no GPC files found under {source_root}")

    observed = collect_output_modes(workspace / "jpn-pc98" / "MES")
    decoded_count = 0
    for name in names:
        source = source_root / name
        if not source.is_file():
            raise FileNotFoundError(source)
        file_output = output / source.name
        modes = observed.get(source.name.upper(), Counter())
        output_mode = args.mode
        if output_mode is None:
            output_mode = modes.most_common(1)[0][0] if modes else 1
        decoded = write_artifacts(
            source,
            file_output,
            output_mode=output_mode,
            observed_modes=dict(modes),
        )
        decoded_count += 1
        print(
            f"{source.name}: {decoded.width}x{decoded.height}, "
            f"mode={decoded.output_mode}, compressed={decoded.compressed_size}"
        )
    print(f"decoded {decoded_count} GPC files into {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
