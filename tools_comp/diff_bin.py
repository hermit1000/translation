import os
from pathlib import Path


def main():
    base_dir = Path("c:/work_han/workspace")
    src_dir = base_dir / "sangoku2-PC98-JPN"
    dst_dir = base_dir / "sangoku2-DOS-KOR"

    # patch_dir = base_dir / "KOUKAI-KOR"
    patch_dir = dst_dir
    dst_dir = patch_dir

    patch_list = os.listdir(patch_dir)
    file_list = os.listdir(src_dir)

    cnt = 0
    for file in file_list:
        src_data_path = f"{src_dir}/{file}"
        dst_data_path = f"{dst_dir}/{file}"

        if file not in patch_list:
            continue

        with open(src_data_path, "rb") as f:
            src_data = f.read()
        with open(dst_data_path, "rb") as f:
            dst_data = f.read()

        msg = ""
        if len(src_data) != len(dst_data):
            msg += f" diff file size ({len(src_data)}, {len(dst_data)}: {len(dst_data) - len(src_data)}) |"

        # if len(msg) > 0:
        #     print(f"{file}\t:{msg}")
        #     cnt += 1
        #     continue
        # continue

        length = min(len(src_data), len(dst_data))
        bin_diff_size = 0
        for i in range(length):
            if src_data[i] != dst_data[i]:
                bin_diff_size += 1
        if bin_diff_size:
            msg += f" diff byte = {bin_diff_size}"
        if msg != "":
            print(f"{file}\t:{msg}")
            cnt += 1

    print(cnt, len(file_list))


if __name__ == "__main__":
    main()
