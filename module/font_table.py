from __future__ import annotations
import hashlib
import json
import logging
import pickle
from copy import deepcopy
from pathlib import Path
from typing import Optional, cast
from .jisx0201 import jisx0201_table

logger = logging.getLogger(__name__)


def get_cached_font_table(
    file_path: Path,
    base_dir: Path,
    custom_char_path: Optional[Path] = None,
) -> FontTable:
    """Load a font table from cache, rebuilding it when its source or custom table changes."""
    custom_path_key = str(custom_char_path.resolve()) if custom_char_path is not None else "no-custom-char"
    custom_path_hash = hashlib.sha256(custom_path_key.encode("utf-8")).hexdigest()[:12]
    custom_path_name = custom_char_path.stem if custom_char_path is not None else "no-custom-char"
    cache_path = base_dir / f"{file_path.stem}-{custom_path_name}-{custom_path_hash}.pkl"

    if cache_path.exists():
        mtime_cache = cache_path.stat().st_mtime
        mtime_font = file_path.stat().st_mtime
        mtime_custom = (
            custom_char_path.stat().st_mtime
            if custom_char_path is not None and custom_char_path.exists()
            else 0
        )

        if mtime_cache > mtime_font and mtime_cache > mtime_custom:
            try:
                with open(cache_path, "rb") as f:
                    return cast(FontTable, pickle.load(f))
            except (pickle.PickleError, EOFError, AttributeError):
                pass  # Create a new cache file when loading fails

    # Create a new cache file and save it
    font_table = FontTable(file_path=file_path, custom_char_path=custom_char_path)
    try:
        with open(cache_path, "wb") as f:
            pickle.dump(font_table, f)
    except Exception:
        pass  # Continue execution even if saving fails

    return font_table


class FontTable:
    def __init__(
        self,
        file_path: Path,
        custom_char_path: Optional[Path] = None,
    ) -> None:
        # Initialize
        self.code2char: dict[str, str] = dict()
        self.char2code: dict[str, str] = dict()
        self.code_int_min = 0xFFFF
        self.code_int_max = 0

        # Check if the file exists
        if not file_path.exists():
            raise FileNotFoundError(f"{file_path} does not exist.")

        # Set code 1 byte (jisx0201)
        self.code2char_ascii = deepcopy(jisx0201_table)
        self.char2code_ascii = {v: k for k, v in self.code2char_ascii.items()}

        # Read font table
        self.read_font_table(file_path)

        # Apply a language-specific custom character table when present.
        if custom_char_path is not None and custom_char_path.exists():
            with open(custom_char_path, "r", encoding="utf-8") as f:
                custom_chars = json.load(f)
            self.set_custom_char(custom_chars)

    def set_custom_char(self, custom_chars: dict = {}) -> None:
        update_1byte = False
        update_2byte = False
        for k, v in custom_chars.items():
            if len(k) == 2:  # 1-byte code
                old_code = self.char2code_ascii.get(v, None)
                if old_code is not None:
                    # To avoid duplicated code and letter
                    self.code2char_ascii.pop(old_code, None)
                self.code2char_ascii[k] = v
                update_1byte = True
            elif len(k) == 4:  # 2-byte code
                old_code = self.char2code.get(v, None)  # To avoid duplicated code and letter
                if old_code is not None:
                    # To avoid duplicated code and letter
                    self.code2char.pop(old_code, None)
                self.code2char[k] = v
                update_2byte = True
            else:
                raise ValueError(f"Invalid code length: {k} during custom char setting.")

        if update_1byte:
            self.char2code_ascii = {v: k for k, v in self.code2char_ascii.items()}
        if update_2byte:
            self.char2code = dict()
            for k, v in self.code2char.items():
                self.char2code.setdefault(v, k)

    def read_font_table(self, file_path: Path) -> bool:
        if not file_path.exists():
            logger.error(f"No {file_path} exist.")
            return False

        ext = file_path.suffix
        if ext == ".tbl":
            self._read_tbl(file_path)
        elif ext == ".json":
            self._read_json(file_path)
        else:
            logger.error(f"{ext} is not a supported format.")
            return False

        # Make char2code table
        self.char2code = dict()
        for k, v in self.code2char.items():
            self.char2code.setdefault(v, k)

        return True

    def write_font_table(self, file_path: Path) -> bool:
        if self.code2char is None:
            logger.error("No font table to write.")
            return False

        ext = file_path.suffix
        if ext == ".tbl":
            self._write_tbl(file_path)
        elif ext == ".json":
            self._write_json(file_path)
        else:
            logger.error(f"{ext} is not a supported format.")
            return False
        return True

    def filter_font(self, character: str) -> None:
        if character in self.char2code_ascii.keys():
            self.char2code_ascii.pop(character)
        if character in self.char2code.keys():
            self.code2char.pop(self.char2code.get(character))

        codes = []
        for code, letter in self.code2char.items():
            if letter == character:
                codes.append(code)
        for code in codes:
            if code in self.code2char.keys():
                self.code2char.pop(code)

    def _read_json(self, file_path: Path):
        with open(file_path, "r", encoding="utf-8") as f:
            font_table = json.load(f)

        codes = list(font_table.keys())
        codes.sort()
        self.code_int_min = int(codes[0], 16)
        self.code_int_max = int(codes[-1], 16)
        self.code2char = font_table

    def _read_tbl(self, file_path: Path) -> None:
        font_table = dict()

        # Read font table
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                line = line.rstrip()
                if "=" not in line:
                    continue
                idx = line.find("=")
                code_hex = line[:idx].upper()
                character = line[idx + 1 :]

                if font_table.get(code_hex) is None:
                    font_table[code_hex] = character
                else:
                    logger.warning(f"duplicated: {code_hex}")

        codes = list(font_table.keys())
        codes.sort()
        self.code_int_min = int(codes[0], 16)
        self.code_int_max = int(codes[-1], 16)
        self.code2char = font_table

    def _read_tbl_1byte(self, file_path: Path) -> None:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

            # Reset 1-byte table
            self.code2char_ascii = dict()
            self.char2code_ascii = dict()

            for line in lines:
                line = line.rstrip()
                idx = line.find("=")
                code_hex = line[:idx].upper()
                character = line[idx + 1 :]

                if self.code2char.get(code_hex) is None:
                    self.code2char_ascii[code_hex] = character
                    self.char2code_ascii[character] = code_hex
                else:
                    logger.warning(f"duplicated: {code_hex}")

    def _write_json(self, file_path: Path) -> None:
        font_table = dict(sorted(self.code2char.items()))
        with open(file_path, "w", encoding="utf-8", newline="\r\n") as f:
            json.dump(font_table, f, ensure_ascii=False, indent=2)

    def _write_tbl(self, file_path: Path) -> None:
        table_for_tbl = ""
        for code, letter in sorted(self.code2char.items()):
            table_for_tbl += f"{code}={letter}\n"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(table_for_tbl)

    def range(self, code_int: int) -> bool:
        return True if self.code_int_min <= code_int <= self.code_int_max else False

    def exists(self, character: str) -> bool:
        return character in self.char2code.keys()

    def exists_1byte(self, character: str) -> bool:
        return character in self.char2code_ascii.keys()

    def is_japanese(self, character: str) -> bool:
        code = self.char2code.get(character)
        code_int = int(code, 16)
        if code_int >= 0x829F and code_int <= 0x8396:
            return True
        return False

    def get_char(self, code_hex: str) -> str:
        return self.code2char.get(code_hex)

    def get_char_ascii(self, code_hex: str) -> str:
        return self.code2char_ascii.get(code_hex)

    def get_chars(self, codes_hex) -> str:
        word = ""
        for code_hex in codes_hex:
            if self.code2char.get(code_hex):
                word += self.code2char.get(code_hex)
            else:
                word += "@"
        return word

    def get_code(self, character: str) -> str:
        return self.char2code.get(character)

    def get_code_ascii(self, character: str) -> str:
        return self.char2code_ascii.get(character)

    def get_codes(self, sentence: str) -> list[str]:
        codes_hex = []
        check_ascii = False
        for character in sentence:
            if character == "|":
                check_ascii = True
                continue
            if check_ascii:
                code_hex = self.char2code_ascii.get(character)
                check_ascii = False
            else:
                code_hex = self.char2code.get(character)
            codes_hex.append(code_hex)

        return codes_hex

    def check_length_from_address(self, address: str) -> int:
        [code_hex_start, code_hex_end] = address.split("=")
        length_from_address = int(code_hex_end, 16) - int(code_hex_start, 16) + 1
        return length_from_address

    def check_length_from_sentence(self, sentence: str, custom_words: dict = None) -> int:
        # Check if the sentence is hex-only
        if "0x:" == sentence[:3]:
            sentence = sentence[3:]  # Remove the hex-only code prefix
            return len(sentence) // 2

        total_length = 0
        i = 0
        while i < len(sentence):
            if sentence[i] == "{":
                end_idx = sentence.find("}", i)
                if end_idx != -1:
                    word = sentence[i + 1 : end_idx]
                    if custom_words and word in custom_words:
                        hex_value = custom_words[word]
                        total_length += len(hex_value) // 2
                        i = end_idx + 1
                        continue
                    else:
                        raise ValueError(
                            f"Custom word '{{{word}}}' not found in provided custom_words for length check."
                        )
                        # print(f"Custom word '{{{word}}}' not found in provided custom_words for length check.")

            character = sentence[i]
            if character == "|":
                if i + 1 < len(sentence):
                    total_length += 1  # The character after '|' is 1-byte
                    i += 1  # Move past the 1-byte character
                else:
                    # Trailing '|' without a character, treat as an error or 0 length.
                    # For now, let's just count 0 for the pipe itself, and next loop will handle past end.
                    pass
            elif character == "@":
                total_length += 2
            else:
                # All other characters are assumed 2-byte
                total_length += 2
            i += 1

        return total_length

    def check_length_from_table(self, sentence: str) -> int:
        length = 0
        for letter in sentence:
            code = self.get_code(letter)
            length += len(code) // 2
        return length

    def verify_sentence(self, sentence: str) -> tuple[int, str]:
        count_false_character = 0
        false_characters = ""
        check_ascii = False

        if "0x:" != sentence[:3]:
            for character in sentence:
                if character == "|":
                    check_ascii = True
                    continue

                if check_ascii:
                    if self.char2code_ascii.get(character) is None:
                        count_false_character += 1
                        false_characters += "|" + character
                    check_ascii = False
                    continue

                if character == "@":  # an ignore character
                    continue

                if character not in self.char2code:
                    count_false_character += 1
                    false_characters += character

        return count_false_character, false_characters
