from pathlib import Path

from module.script import Script


def main():
    platform = "dos"
    # platform = "pc98"

    script_base_dir = Path(f"../workspace0/script-{platform}")
    src_bin_base_dir = Path(f"../workspace0/jpn-{platform}")

    # ===================================================================
    for file in script_base_dir.glob("*.json"):  # Use rglob to search subdirectories
        if "_kor.json" not in file.name:
            continue

        # Check paths
        dst_script_path = file
        src_script_path = file.parent / file.name.replace("_kor.json", "_jpn.json")
        if not src_script_path.exists():
            print(f"{src_script_path.name} is not exists.")
            continue

        # Check a source data path
        src_data_path = src_bin_base_dir / str(file.relative_to(script_base_dir)).replace("_kor.json", "")
        if not src_data_path.exists():
            print(f"{src_data_path.name} is not exists.")
            continue

        # Read source and destination script
        src_script = Script(str(src_script_path))
        dst_script = Script(str(dst_script_path))

        # Compare addresses in the source and destination scripts
        count_diff = src_script.diff_addresses(dst_script.script)
        if count_diff:
            return

        src_script.save(src_script_path)
        dst_script.save(file)

        print(1)


if __name__ == "__main__":
    main()
