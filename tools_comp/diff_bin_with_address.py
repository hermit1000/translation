from pathlib import Path
from module.script import Script


def main():
    platform = "pc98"
    ws_num = 5
    base_dir = Path(f"c:/work_han/workspace{ws_num}")

    script_base_dir = base_dir / f"script-{platform}"
    src_bin_base_dir = base_dir / f"jpn-{platform}"
    dst_bin_base_dir = base_dir / f"kor-{platform}"

    for file in script_base_dir.rglob("*.json"):  # Use rglob to search subdirectories
        if "_jpn.json" not in file.name:
            continue

        if "MAIN.EXE" not in file.name:
            continue

        bin_name = str(file.relative_to(script_base_dir)).replace("_jpn.json", "")
        src_bin_path = src_bin_base_dir / bin_name
        dst_bin_path = dst_bin_base_dir / bin_name

        with open(src_bin_path, "rb") as f:
            src_bin = bytearray(f.read())
        with open(dst_bin_path, "rb") as f:
            dst_bin = bytearray(f.read())

        address_list = []
        for address, sentence in Script(str(file)).script.items():
            start, end = address.split("=")
            start = int(start, 16)
            end = int(end, 16)
            address_list.append((start, end))

        length = min(len(src_bin), len(dst_bin))
        for i in range(length):
            if src_bin[i] == dst_bin[i]:
                continue

            is_existing_range = False
            for start, end in address_list:
                if start <= i <= end:
                    is_existing_range = True
                    break
            if is_existing_range:
                continue
            print(f"{file.name}\t{i:04x}\t{src_bin[i]:02x}\t{dst_bin[i]:02x}")


if __name__ == "__main__":
    main()
