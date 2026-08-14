from pathlib import Path
from module.script import Script


def main():
    platform_dst = "dos"
    platform = "pc98"
    ws_num = 1
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_base_dir = base_dir / f"script-{platform}"
    dst_script_base_dir = base_dir / f"script-{platform_dst}"

    src_bin_base_dir = base_dir / f"jpn-{platform}"
    dst_bin_base_dir = base_dir / f"jpn-{platform_dst}"

    target = "MAIN.EXE"

    src_jpn_script_path = script_base_dir / f"{target}_jpn.json"
    src_kor_script_path = script_base_dir / f"{target}_kor.json"
    src_bin_path = src_bin_base_dir / target
    dst_bin_path = dst_bin_base_dir / target
    dst_jpn_script_path = dst_script_base_dir / src_jpn_script_path.name
    dst_kor_script_path = dst_script_base_dir / src_kor_script_path.name

    src_jpn_script = Script(str(src_jpn_script_path))
    src_kor_script = Script(str(src_kor_script_path))
    dst_jpn_script = Script()
    dst_kor_script = Script()

    src_bin = bytearray(open(src_bin_path, "rb").read())
    dst_bin = bytearray(open(dst_bin_path, "rb").read())
    # src_font_table = FontTable(src_font_table_path, script_base_dir)

    pos = 0
    for address, content_jpn in src_jpn_script.script.items():
        sentence_jpn = content_jpn.text
        start, end = address.split("=")
        start = int(start, 16)
        end = int(end, 16)
        length = end - start + 1

        if "0x:" in sentence_jpn:
            # combined_hex = sentence_jpn.replace("0x:", "")
            continue

        # Extract bytes from source string
        # hex_strings = src_font_table.get_codes(sentence_jpn)
        # combined_hex = "".join(hex_strings)
        # result_byt = bytearray.fromhex(combined_hex)

        if length > 20:
            target_hex = src_bin[start : end + 1]
        else:
            target_hex = src_bin[start : start + 20]

        # Find matches
        position = dst_bin[pos:].find(target_hex)
        if position == -1:
            position = dst_bin.find(target_hex)
        else:
            position = position + pos
        if position == -1:
            print(f"Can't find match: {address}:{sentence_jpn}")
            continue

        start_new = position
        end_new = position + length - 1
        address_new = f"{start_new:05X}={end_new:05X}"

        # Check if it is already found
        if address_new not in dst_jpn_script.script:
            dst_jpn_script.script[address_new] = content_jpn.copy()
            dst_kor_script.script[address_new] = src_kor_script.script[address].copy()
        pos = end_new + 1

    dst_jpn_script.save(dst_jpn_script_path)
    dst_kor_script.save(dst_kor_script_path)


if __name__ == "__main__":
    main()
