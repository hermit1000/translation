import argparse
import cv2
import struct
import numpy as np
from pathlib import Path
from gspecific.image_workspace import ImageWorkspace, native_artifact_name, update_meta
from module.pc98_image.planar import decode_plane_major_row_planar


def read_img(file_path: Path) -> tuple:
    """
    Reads a .IMG file and returns the tag, width, height, and compresssed_data data.
    """
    with open(file_path, "rb") as f:
        tag, w, h = struct.unpack("<HHH", f.read(6))
        compresssed_data = bytearray(f.read())
    return tag, (w + 1) * 8, h + 1, compresssed_data


def decompress_img(raw: bytearray, width: int, height: int) -> bytearray:
    """
    Decompresses a .IMG file and returns the decompressed data.
    """
    width_4bpp = width // 8
    w = width_4bpp - 1
    h = height - 1

    planar_data = bytearray(height * width_4bpp * 4)

    buf_return = (h) * width_4bpp
    raw_idx = 0
    buf_idx = 0
    h_idx = h
    w_idx = w
    ah = 0

    while raw_idx < len(raw):
        al = raw[raw_idx]
        raw_idx += 1
        if al != 0:  # Direct update
            ah = ah ^ al  # to keep delta value instead of absolute value
            planar_data[buf_idx] = ah

            # Check boundary conditions
            if h_idx < 1:
                buf_idx -= buf_return
                buf_idx += 1
                w_idx -= 1
                h_idx = h
            else:
                buf_idx += width_4bpp
                h_idx -= 1
            if w_idx < 0:
                w_idx = w
                buf_idx += buf_return
        else:  # RLE decoding when al == 0
            al = raw[raw_idx]
            raw_idx += 1

            if al == 0:  # bl is big...
                al = raw[raw_idx]
                raw_idx += 1
                bl = al
                al = raw[raw_idx]
                raw_idx += 1
                bl += al * 256
            else:  # al != 0
                bl = al
            for k in range(bl):
                planar_data[buf_idx] = ah

                # Check boundary conditions
                if h_idx < 1:
                    buf_idx -= buf_return
                    buf_idx += 1
                    w_idx -= 1
                    h_idx = h
                else:
                    buf_idx += width_4bpp
                    h_idx -= 1
                if w_idx < 0:
                    w_idx = w
                    buf_idx += buf_return

    return planar_data


def main():
    parser = argparse.ArgumentParser(description="Decode Mac1 IMG files from a workspace")
    parser.add_argument(
        "--workspace",
        required=True,
        type=Path,
        help="workspace containing jpn-pc98 and image-pc98",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="IMG filenames relative to jpn-pc98",
    )
    args = parser.parse_args()
    workspace = ImageWorkspace(args.workspace)

    for relative_source in args.inputs:
        file_path = workspace.source(relative_source)
        output_dir = workspace.artifacts(relative_source)
        tag, width, height, compressed_data = read_img(file_path)
        planar_data = decompress_img(compressed_data, width, height)
        indexed_data = decode_plane_major_row_planar(
            planar_data, width, height, 4
        )
        image = np.frombuffer(indexed_data, dtype=np.uint8).reshape((height, width))
        grayscale = (image * 17).astype(np.uint8)
        stem = file_path.stem

        (output_dir / native_artifact_name(file_path.name, "jpn")).write_bytes(
            file_path.read_bytes()
        )
        (output_dir / f"{stem}.pln.jpn.bin").write_bytes(planar_data)
        (output_dir / f"{stem}.idx.jpn.bin").write_bytes(indexed_data)
        output_png = output_dir / f"{stem}.jpn.png"
        if not cv2.imwrite(str(output_png), grayscale):
            raise OSError(f"failed to write {output_png}")
        update_meta(
            output_dir / f"{stem}.meta.json",
            source=str(relative_source),
            offset="0x000000",
            original_size=file_path.stat().st_size,
            encoded_size=None,
            stored_size=None,
            padding_byte=None,
            compression="mac1-xor-delta-rle",
            tag=tag,
            width=width,
            height=height,
            planes=4,
            plane_order="BRGI",
            planar_layout="plane-major-row",
            bit_order="msb-first",
            stride=width // 8,
            palette="grayscale-index-0-15",
        )
        print(output_png)


if __name__ == "__main__":
    main()
