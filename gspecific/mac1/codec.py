import argparse
import struct
from pathlib import Path
from gspecific.image_workspace import ImageWorkspace
from gspecific.mac1.decode import read_img


def generate_traversal_order(w: int, h: int) -> list[int]:
    """
    Generates the list of buffer indices in the same column-major
    order used by the original decompression algorithm.
    """
    width_4bpp = w + 1  # 30 for w=29
    height = h + 1  # 100 for h=99
    plane_size = width_4bpp * height  # 3000

    indices = []

    for plane in range(4):
        plane_offset = plane * plane_size
        for col in range(w + 1):
            for row in range(h + 1):
                idx = plane_offset + (row * width_4bpp) + col
                indices.append(idx)
    return indices


def compress_mac1(raw_data: bytearray, traversal_indices: list[int]) -> bytearray:
    """
    Compresses raw 4BPP data using the custom Delta + RLE algorithm,
    following the provided traversal order.
    """
    compressed = bytearray()
    ah = 0  # Represents the last value encoded

    idx = 0
    data_len = len(traversal_indices)

    while idx < data_len:
        current_buf_pos = traversal_indices[idx]

        # --- 1. RLE Lookahead ---
        # Check for a run of the last encoded value 'ah'
        run_length = 0
        lookahead_idx = idx
        while lookahead_idx < data_len and raw_data[traversal_indices[lookahead_idx]] == ah:
            run_length += 1
            lookahead_idx += 1

        if run_length > 0:
            # Encode the run
            # The original seems to favor RLE even for short runs.
            while run_length > 0:
                chunk_len = min(run_length, 65535)

                compressed.append(0)  # RLE marker

                if chunk_len > 255:
                    compressed.append(0)  # Long run marker
                    compressed.extend(struct.pack("<H", chunk_len))
                else:
                    compressed.append(chunk_len)  # Short run

                idx += chunk_len
                run_length -= chunk_len
            continue

        # --- 2. Delta Encoding ---
        # If no RLE run was found, encode the current byte as a delta
        if idx < data_len:
            current_value = raw_data[current_buf_pos]
            delta = ah ^ current_value
            # A delta of 0 would be mistaken for an RLE block, but this only
            # happens if current_value == ah, which is handled by the RLE block.
            compressed.append(delta)
            ah = current_value
            idx += 1

    return compressed


def main():
    """
    Main function to run the encoder and verify the output.
    """
    parser = argparse.ArgumentParser(
        description="Verify Mac1 compression against a workspace IMG"
    )
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("input", help="IMG filename relative to jpn-pc98")
    args = parser.parse_args()
    workspace = ImageWorkspace(args.workspace)
    reference_file = workspace.source(args.input)
    artifact_dir = workspace.artifacts(args.input)
    input_file = artifact_dir / f"{reference_file.stem}.pln.jpn.bin"

    print(f"Reading raw data from: {input_file}")
    try:
        with open(input_file, "rb") as f:
            raw_data = bytearray(f.read())
    except FileNotFoundError:
        print(f"Error: Input file not found at {input_file}")
        return

    print(f"Reading dimensions from reference file: {reference_file}")
    try:
        tag, w, h, reference_payload = read_img(reference_file)
    except FileNotFoundError:
        print(f"Error: Reference file not found at {reference_file}")
        return

    print(f"Dimensions: w={w}, h={h}. Generating column-major traversal order...")
    traversal_indices = generate_traversal_order((w // 8) - 1, h - 1)

    # Quick sanity check
    expected_size = w * h // 2
    if len(traversal_indices) != expected_size:
        print(f"Error: Traversal size ({len(traversal_indices)}) does not match expected size ({expected_size})")
        return

    print("Compressing data...")
    compressed_data = compress_mac1(raw_data, traversal_indices)
    print(f"Compression complete. Output size: {len(compressed_data)} bytes.")

    print("Comparing generated data with reference data...")

    if compressed_data == reference_payload:
        print("\n[SUCCESS] The generated compressed data matches the reference MG09.IMG payload.")
    else:
        print("\n[FAILURE] The generated compressed data does NOT match the reference file.")
        print(f"Generated length: {len(compressed_data)}")
        print(f"Reference length: {len(reference_payload)}")

        # Find the first point of difference
        for i, (gen_byte, ref_byte) in enumerate(zip(compressed_data, reference_payload)):
            if gen_byte != ref_byte:
                print(f"Mismatch found at offset {i}:")
                print(f"  - Generated: {gen_byte:#04x}")
                print(f"  - Reference: {ref_byte:#04x}")

                # Show some context
                start = max(0, i - 10)
                end = min(len(compressed_data), i + 10)
                print("\nContext (Generated):")
                print(f"... {' '.join(f'{b:02x}' for b in compressed_data[start:end])} ...")

                print("\nContext (Reference):")
                print(f"... {' '.join(f'{b:02x}' for b in reference_payload[start:end])} ...")
                break

        # Check if one is a prefix of the other
        if len(compressed_data) != len(reference_payload):
            print("\nFiles have different lengths.")
            if len(compressed_data) > len(reference_payload) and compressed_data.startswith(reference_payload):
                print("Reference is a prefix of Generated.")
            elif len(reference_payload) > len(compressed_data) and reference_payload.startswith(compressed_data):
                print("Generated is a prefix of Reference.")


if __name__ == "__main__":
    main()
