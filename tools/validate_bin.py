from pathlib import Path
from module.script import Script
from module.font_table import FontTable
from rich.console import Console


def main():
    ws_num = 4
    platform = "pc98"
    base_dir = Path(f"c:/work_han/workspace{ws_num}")
    script_base_dir = base_dir / f"script-{platform}"
    src_bin_base_dir = base_dir / f"jpn-{platform}"
    src_font_table_path = Path("font_table/font_table-jpn.json")
    src_font_table = FontTable(src_font_table_path)

    console = Console()
    for file in script_base_dir.glob("*.json"):  # Use rglob to search subdirectories
        if "OPEN" not in file.name:
            continue

        if "_jpn.json" not in file.name:
            continue

        print(file.name)

        # Check paths
        script_path = file
        # Check a source data path
        src_data_path = src_bin_base_dir / str(file.relative_to(script_base_dir)).replace("_jpn.json", "")
        if not src_data_path.exists():
            print(f"{src_data_path.name} is not exists.")
            continue

        # Read a script
        script = Script(str(script_path))

        # Read the source binary data
        if not Path(src_data_path).exists():
            return
        with open(src_data_path, "rb") as f:
            data = f.read()
        data = bytearray(data)
        console.print(f"Data size: {src_data_path}({len(data):,} bytes)")

        is_diff = script.validate_with_binary(font_table=src_font_table, binary_data=data)
        if is_diff:
            console.print(f"[yellow] json and data doesn't match.[/yellow] [green]{src_data_path}[/green]")
        else:
            console.print(f"[green] json and data match.[/green] [green]{src_data_path}[/green]")


if __name__ == "__main__":
    main()
