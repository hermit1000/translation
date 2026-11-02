"""Build FQ3 PC-98 Korean files from the packed Japanese originals.

MAIN.EXE is unpacked in memory, patched at decoded JSON addresses, and
repacked with its original EXEPACK loader. END.BIN uses its own two-stage
codec. The other script files are patched at their file addresses.

Run: python -m gspecific.fq.fq3.write_lang [workspace] [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from module.font_table import get_cached_font_table
from module.script import Script

from gspecific.fq.fq3.build_end import build_bytes as build_end_bytes
from gspecific.fq.fq3.build_gdata import build_bytes as build_gdata_bytes
from gspecific.fq.fq3.repack_main import repack
from gspecific.fq.fq3.render_patch import patch_image, patch_open_exe
from gspecific.fq.fq3.unpack_main import unpack, word


WORKSPACE = Path(r"C:\work_han\workspace13")
SCRIPT_FILES = ("FQ3MES.DAT", "HITOBUF.DAT", "MAIN.EXE", "OPEN.EXE")


def custom_words(script_dir: Path, language: str) -> dict[str, str]:
    words = {}
    for name in ("custom_word.json", f"custom_word_{language}.json",
                 f"custom_word_ext_{language}.json"):
        path = script_dir / name
        if path.exists():
            words.update(json.loads(path.read_text(encoding="utf-8")))
    return words


def build_outputs(workspace: Path) -> dict[str, bytes]:
    script_dir = workspace / "script-pc98"
    source_dir = workspace / "jpn-pc98"
    code_root = Path(__file__).resolve().parents[3]
    src_font = get_cached_font_table(
        code_root / "font_table/font_table-jpn.json", workspace,
        script_dir / "custom_char.json")
    dst_font = get_cached_font_table(
        code_root / "font_table/font_table-kor-jin.json", workspace,
        script_dir / "custom_char.json")
    src_words = custom_words(script_dir, "jpn")
    dst_words = custom_words(script_dir, "kor")
    outputs = {}
    for name in SCRIPT_FILES:
        src_script = Script(str(script_dir / f"{name}_jpn.json"))
        dst_script = Script(str(script_dir / f"{name}_kor.json"))
        if src_script.script.keys() != dst_script.script.keys():
            raise ValueError(f"Japanese/Korean addresses differ: {name}")
        if name == "MAIN.EXE":
            packed = (source_dir / name).read_bytes()
            executable, image = unpack(packed)
            header_size = word(executable, 8) * 16
            source = executable[:header_size] + patch_image(image)
        else:
            packed = None
            header_size = 0
            source = (source_dir / name).read_bytes()
        data = src_script.apply_zero_padding(bytearray(source))
        if src_script.validate_with_binary(src_font, binary_data=data.copy(),
                                           custom_words=src_words):
            raise ValueError(f"Japanese JSON differs from source: {name}")
        data, count = dst_script.write_script(
            data=data, font_table=dst_font, custom_words=dst_words,
            binary_input_dir=workspace / "binary_inputs-pc98")
        if count != len(dst_script.script):
            raise ValueError(f"only {count}/{len(dst_script.script)} fields encoded: {name}")
        if packed is not None:
            if len(data) != len(source):
                raise ValueError("translated unpacked MAIN.EXE changed size")
            outputs[name] = repack(packed, bytes(data[header_size:]))
        else:
            outputs[name] = patch_open_exe(bytes(data)) if name == "OPEN.EXE" else bytes(data)
        print(f"{name}: {count}/{len(dst_script.script)} fields, {len(outputs[name])} bytes")
    outputs["END.BIN"] = build_end_bytes(workspace)
    print(f"END.BIN: {len(outputs['END.BIN'])} bytes")
    outputs["GDATA.CHR"] = build_gdata_bytes(workspace)
    print(f"GDATA.CHR: {len(outputs['GDATA.CHR'])} bytes")
    return outputs


def write_lang(workspace: Path, output: Path | None = None,
               check: bool = False) -> dict[str, bytes]:
    outputs = build_outputs(workspace)
    if check:
        return outputs
    destinations = [output or workspace / "kor-pc98"]
    if output is None:
        destinations.append(workspace / "kor-pc98-dosbox-x")
    for directory in destinations:
        directory.mkdir(parents=True, exist_ok=True)
        for name, data in outputs.items():
            (directory / name).write_bytes(data)
        print(f"Wrote {len(outputs)} files to {directory}")
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=WORKSPACE)
    parser.add_argument("--output", type=Path, help="output directory; defaults to kor-pc98")
    parser.add_argument("--check", action="store_true", help="build and validate without writing")
    args = parser.parse_args()
    write_lang(args.workspace.resolve(), args.output, args.check)


if __name__ == "__main__":
    main()
