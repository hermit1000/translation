# Translation Toolkit

A modern Python package for reverse engineering and translating Japanese video games into Korean.

## Features
- **Script Extraction**: Extract Japanese text from binary files with font table support.
- **Script Injection**: Inject translated Korean text back into game binaries.
- **Font Management**: Handle custom font tables (.tbl, .json) and font image generation.
- **Encoding Support**: Built-in support for common encoding/decoding schemes (e.g., XOR).
- **Name Database**: Manage character names for consistent translation.

## Installation

### Requirements
- Python 3.9+

### Setup
1. Clone the repository:
   ```bash
   git clone git@github:ybaik/translation.git
   cd translation
   ```

2. Install the package and development dependencies:
   ```bash
   python -m pip install -e ".[dev]"
   ```

3. Install the Git pre-commit hook:
   ```bash
   python -m pre_commit install --install-hooks
   ```

   Run both commands in the same Python environment and shell used for
   `git commit`. For example, if commits are created from Windows Git Bash,
   install the hook from Windows Git Bash rather than WSL.

4. Verify the hook:
   ```bash
   python -m pre_commit run --all-files
   ```

This installs the runtime dependencies (`fonttools`, `numpy`, `pillow`,
`opencv-python`, and `rich`) and development tools (`pytest`, `ruff`, and
`pre-commit`).

To install only the package and runtime dependencies:
```bash
python -m pip install -e .
```

## Usage

The automation scripts use a workspace next to this repository. Before
running them, read [Workspace structure](doc/workspace_structure.md) and set
the target `ws_num` and `platform` values near the top of each script's
`main()` function.

Typical text workflow:

```text
jpn-<platform>/
  -> extract_script_auto.py
script_init-<platform>/
  -> select files and create translations
script-<platform>/
  -> write_script_auto.py
kor-<platform>/
```

### 1. Prepare the workspace

Place the original game binaries under
`workspace<N>/jpn-<platform>/`, preserving their relative paths. Configure
`ws_num` and `platform` in `extract_script_auto.py` for that workspace.

### 2. Extract the initial scripts

```bash
python extract_script_auto.py
```

The extracted `*_jpn.json` files are written to
`script_init-<platform>/`. This directory is a regenerable extraction result,
not the translation workspace.

### 3. Select and translate scripts

Copy the files being translated from `script_init-<platform>/` to
`script-<platform>/`, preserving their relative paths. Keep the Japanese
`*_jpn.json` file and create a paired `*_kor.json` file.

Translation must preserve address ranges, byte lengths, control codes, and
supported characters. Follow the
[translation strategy and validation rules](doc/translation_strategy.md)
before writing translated data.

Place script-specific mapping files in `script-<platform>/`:

- `custom_char.json`: character-code overrides shared by source and output
  font tables.
- `custom_word.json`: Korean byte substitutions and custom one-byte
  sequences.

### 4. Build the translated binaries

Configure the same `ws_num` and `platform` in `write_script_auto.py`, then
run:

```bash
python write_script_auto.py
```

The script reads the original files from `jpn-<platform>/`, applies the
paired files under `script-<platform>/`, and writes results to
`kor-<platform>/`. Binary replacement assets referenced by script metadata
must be placed under `binary_inputs-<platform>/`.

Do not treat output under `kor-<platform>/` as the source of later builds;
each build starts from the original files under `jpn-<platform>/`.

### 5. Convert game images

Image work uses `image-pc98/` and `image-dos/` independently. Naming,
metadata, decode/encode stages, palette requirements, and supported formats
are documented in [Image conversion](doc/image_conversion.md).

## Documentation

- [Workspace structure and generated files](doc/workspace_structure.md)
- [Translation strategy and validation rules](doc/translation_strategy.md)
- [Image conversion workflow and formats](doc/image_conversion.md)

## Project Structure

- `module/`: Core script, font-table, compression, and image codecs.
- `gspecific/`: Game-specific codecs and conversion tools.
- `tools*/`: Analysis, editing, font, image, and validation utilities.
- `font_table/`: Shared Japanese and Korean character tables.
- `name_db/`: Character, region, and item name databases.
- `tests/`: Automated codec and database tests.
- `doc/`: Workspace, translation, and image workflow documentation.

## License
MIT License
