# Description: Converts workspace Korean PNG files to the custom compressed IMG format.
# Requirements: opencv-python, numpy

import argparse
import cv2
import struct
from pathlib import Path
from gspecific.image_workspace import ImageWorkspace, native_artifact_name, update_meta
from module.pc98_image.planar import encode_plane_major_row_planar

# Import the compression logic from the previously created comp.py
from gspecific.mac1.codec import compress_mac1, generate_traversal_order


def process_image(source_path: Path, image_path: Path, output_dir: Path):
    """
    Reads a Korean PNG, converts it, and saves a Korean IMG artifact.
    """
    stem = source_path.stem
    output_img_path = output_dir / native_artifact_name(source_path.name, "kor")

    # 1. Read header and dimensions from original .IMG file
    print(f"Reading header from: {source_path}")
    with open(source_path, "rb") as f:
        header = f.read(6)
        _tag, w, h = struct.unpack("<HHH", header)

    print(f"Dimensions from header: w={w}, h={h}")

    # 2. Read the grayscale BMP image
    print(f"Reading grayscale image: {image_path}")
    gray_image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if gray_image is None:
        raise FileNotFoundError(image_path)

    # 3. Convert 8-bit grayscale (0-255) to 4-bit indices (0-15)
    print("Converting image to 4-bit indices...")
    data_8bpp = gray_image // 17

    # Check dimensions. The image dimensions should match the header info.
    # IMG dimensions are (w+1)*8 by (h+1)
    expected_height = h + 1
    expected_width = (w + 1) * 8
    if gray_image.shape[0] != expected_height or gray_image.shape[1] != expected_width:
        print(
            f"Warning: Image dimensions ({gray_image.shape[1]}x{gray_image.shape[0]}) do not match expected ({expected_width}x{expected_height})"
        )

    # 4. Convert indexed image to 4BPP planar format
    print("Converting to 4BPP planar format...")
    planar_data = encode_plane_major_row_planar(
        data_8bpp.tobytes(), expected_width, expected_height, 4
    )

    # 5. Generate traversal order for compression
    print("Generating traversal order...")
    traversal_indices = generate_traversal_order(w, h)

    # 6. Compress the planar data
    print("Compressing data...")
    compressed_data = compress_mac1(planar_data, traversal_indices)
    print(f"Compression complete. Compressed size: {len(compressed_data)} bytes.")

    # 7. Write the new .IMG file
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{stem}.idx.kor.bin").write_bytes(data_8bpp.tobytes())
    (output_dir / f"{stem}.pln.kor.bin").write_bytes(planar_data)
    print(f"Writing new file: {output_img_path}")
    with open(output_img_path, "wb") as f:
        f.write(header)
        f.write(compressed_data)
    update_meta(
        output_dir / f"{stem}.meta.json",
        encoded_size=output_img_path.stat().st_size,
        stored_size=output_img_path.stat().st_size,
        padding_byte=None,
    )
    print(f"[SUCCESS] Successfully created {output_img_path}\n")


def main():
    parser = argparse.ArgumentParser(description="Encode Mac1 IMG files in a workspace")
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
        source_path = workspace.source(relative_source)
        output_dir = workspace.artifacts(relative_source)
        image_path = output_dir / f"{source_path.stem}.kor.png"
        if not image_path.exists():
            print(f"skip: {image_path} does not exist")
            continue
        process_image(source_path, image_path, output_dir)


if __name__ == "__main__":
    main()
