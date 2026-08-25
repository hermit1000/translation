import os
import json
from pathlib import Path
from rich import box
from rich.table import Table
from rich.console import Console
from module.script import Script
from module.font_table import get_cached_font_table


skip_list = []


def load_custom_words(script_base_dir: Path, language: str) -> dict:
    language_path = script_base_dir / f"custom_word_{language}.json"
    ext_path = script_base_dir / f"custom_word_ext_{language}.json"
    common_path = script_base_dir / "custom_word.json"
    custom_words = {}
    if common_path.exists():
        with open(common_path, "r", encoding="utf-8") as f:
            custom_words.update(json.load(f))
    if language_path.exists():
        with open(language_path, "r", encoding="utf-8") as f:
            custom_words.update(json.load(f))
    if ext_path.exists():
        with open(ext_path, "r", encoding="utf-8") as f:
            custom_words.update(json.load(f))
    return custom_words


def main():
    platform = "dos"
    # platform = "pc98"
    ws_num = 1
    tag = ""
    copy_subdir = ""
    # tag = "-384k"
    # copy_subdir = "RW"

    global skip_list

    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_base_dir = base_dir / f"script-{platform}{tag}"
    src_bin_base_dir = base_dir / f"jpn-{platform}{tag}"
    dst_bin_base_dir = base_dir / f"kor-{platform}{tag}"

    binary_input_dir = base_dir / f"binary_inputs-{platform}"
    src_font_table_path = Path("font_table/font_table-jpn.json")
    dst_font_table_path = Path("font_table/font_table-kor-jin.json")

    # ===================================================================
    # For debugging prints
    console = Console()
    table = Table(box=box.SIMPLE_HEAD)
    table.add_column("파일", justify="left")
    table.add_column("진행률", justify="right")
    table.add_column("비고", justify="right")

    total_valid = 0
    total_count = 0
    total_valid_file = 0
    total_count_file = 0

    completed_list = []

    # if (base_dir / "complete_list.txt").exists():
    #     with open(base_dir / "complete_list.txt", "r") as f:
    #         skip_list += f.read().splitlines()
    #         skip_list = list(set(skip_list))

    src_custom_words = load_custom_words(script_base_dir, "jpn")
    dst_custom_words = load_custom_words(script_base_dir, "kor")

    for file in script_base_dir.rglob("*.json"):  # Use rglob to search subdirectories
        if "_kor.json" not in file.name:
            continue

        # if "MAIN.EXE" not in file.name:
        #     continue
        # if "BGSET.EXE" not in file.name:
        #     continue

        org_fn = file.name.replace("_kor.json", "")
        if org_fn in skip_list:
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

        # Check a destination data path
        dst_data_path = dst_bin_base_dir / src_data_path.relative_to(src_bin_base_dir)
        # if dst_data_path.exists():
        #     continue

        if not dst_data_path.parent.exists():
            dst_data_path.parent.mkdir(parents=True, exist_ok=True)

        console.print(f"[yellow] Start:{src_data_path}[/yellow]")

        # Read source and destination font tables
        src_font_table = get_cached_font_table(
            file_path=src_font_table_path,
            base_dir=base_dir,
            custom_char_path=script_base_dir / "custom_char.json",
        )
        dst_font_table = get_cached_font_table(
            file_path=dst_font_table_path,
            base_dir=base_dir,
            custom_char_path=script_base_dir / "custom_char.json",
        )

        # Read source and destination script
        src_script = Script(str(src_script_path))
        dst_script = Script(str(dst_script_path))

        # Read the source binary data
        if not Path(src_data_path).exists():
            return
        with open(src_data_path, "rb") as f:
            data = f.read()
        data = bytearray(data)
        console.print(f"Data size: {src_data_path}({len(data):,} bytes)")

        # Check and apply binary expansion options based on the contents of the source script.
        data = src_script.apply_zero_padding(data)

        # Compare addresses in the source and destination scripts
        count_diff = src_script.diff_addresses(dst_script.script)
        if count_diff:
            return

        # Check the destination script
        # count_false_length, count_false_letters = dst_script.validate(dst_font_table)

        # if count_false_length:
        #     console.print(f"[yellow] False length/letter count:{count_false_length},{count_false_letters}[/yellow]")
        # if count_false_letters:
        #     console.print(f"[yellow] False length/letter count:{count_false_length},{count_false_letters}[/yellow]")
        #     return

        # print(f"False length/letter count:{count_false_length},{count_false_letters}")
        # console.print(f"[yellow] End:{src_data_path}[/yellow]")

        # Check source script with binary data
        is_diff = src_script.validate_with_binary(
            font_table=src_font_table,
            binary_data=data.copy(),
            custom_words=src_custom_words,
        )
        if is_diff:
            console.print(f"[yellow] json and data doesn't match.[/yellow] [green]{src_data_path}[/green]")
        else:
            console.print(f"[green] json and data match.[/green] [green]{src_data_path}[/green]")

        # Write the destination script to the binary data in memory
        data, valid_sentence_count = dst_script.write_script(
            data=data, font_table=dst_font_table, custom_words=dst_custom_words, binary_input_dir=binary_input_dir
        )
        if len(dst_script.script):
            valid_p = valid_sentence_count / len(dst_script.script) * 100
            total_valid += valid_sentence_count
            total_count += len(dst_script.script)
            total_count_file += 1
            precision = 1 if valid_p >= 100 else 2
            style = None if precision == 1 else "#00e5ff"
            table.add_row(
                file.name.replace("_kor.json", ""),
                f"{valid_p:.{precision}f} %",
                f"{valid_sentence_count}/{len(dst_script.script)}",
                style=style,
            )
            completed_list.append((src_data_path, valid_p))
            if valid_p == 100:
                total_valid_file += 1

        # Save the replaced binary data to a file in the destination directory
        with open(dst_data_path, "wb") as f:
            f.write(data)

    if f"workspace{ws_num}\\" in str(script_base_dir):
        emul = "dosbox-x" if platform == "pc98" else "dosbox"
        cmd = (
            f"xcopy /E /I /Y ..\\workspace{ws_num}\\kor-{platform}{tag}\\."
            f" ..\\workspace{ws_num}\\kor-{platform}-{emul}\\{copy_subdir}\\"
        )
        os.system(cmd)

    if total_count:
        # Print remaining sentences among not completed files
        percentage = total_valid / total_count * 100
        precision = 1 if percentage >= 100 else 2
        table.add_row("Total", f"{percentage:.{precision}f} %", f"{total_valid}/{total_count}", style="bold yellow")

        # Print the status of total files
        total_valid_file += len(skip_list)
        total_count_file += len(skip_list)
        percentage = total_valid_file / total_count_file * 100
        console.print(f"Total files: {total_valid_file}/{total_count_file} ({percentage:.2f}))%")

        for i, (file, percent) in enumerate(completed_list):
            color = "green" if percent == 100 else "yellow"
            console.print(f"[{color}]{i + 1}[/{color}] {file.name}, {percent:.2f}")
    console.print(table)


if __name__ == "__main__":
    main()
