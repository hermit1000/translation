import os
from pathlib import Path
from module.font_table import FontTable
from module.script import Script
from module.decoding import decode


def main():
    ws_num = 0
    workspace = f"workspace{ws_num}"
    platform = "pc98"
    bin_dir = Path(f"../{workspace}/jpn-{platform}")
    font_table_path = Path("font_table/font_table-jpn.json")
    extended_word = "_jpn"
    script_init_dir = Path(f"../{workspace}/script_init-{platform}")

    # dos kor
    # bin_path = f"../{workspace}/kor-{platform}"
    # font_table_path = f"../{workspace}/font_table-kor-suho.tbl"
    # extended_word = "_kor"
    # script_path = f"../{workspace}/script_init-{platform}"

    length_threshold_in_bytes = 2
    check_ascii = True
    check_ascii_restriction = False  # If True, the first ASCII code needs to be x20

    decoding_enable = False
    # decoding_info = "xor:0x83"
    decoding_info = "lzss:gss2"
    decoding_base_path = f"../{workspace}/jpn-{platform}-decoded"
    # =================================================================

    for file in bin_dir.rglob("*"):
        src_data_path = file
        dst_script_path = script_init_dir / (str(file.relative_to(bin_dir)) + extended_word + ".json")

        if not dst_script_path.parent.exists():
            dst_script_path.parent.mkdir(parents=True, exist_ok=True)

        # if "SCEDATA" not in file.name:
        #     continue

        # if file.suffix not in [".TBZ"]:
        #     continue

        if not os.path.isfile(src_data_path):
            continue

        print(f"{file} ===========================================")
        # Read a font table
        font_table = FontTable(font_table_path)

        # Read a target binary data
        with open(src_data_path, "rb") as f:
            data = f.read()
        data = bytearray(data)

        # Decoding
        if decoding_enable:
            data = decode(data, decoding_info)
            decoding_path = f"{decoding_base_path}/{file.name}"
            with open(decoding_path, "wb") as f:
                f.write(data)
            continue

        print(f"Data size: {src_data_path}({len(data):,} bytes)")

        # Extract a script from the binary data
        script = Script()
        script.extract_script(
            data=data,
            font_table=font_table,
            length_threshold=length_threshold_in_bytes,
            check_ascii=check_ascii,
            check_ascii_restriction=check_ascii_restriction,
        )

        # Save the extracted script to a file in the script directory
        script.save(dst_script_path)


if __name__ == "__main__":
    main()
