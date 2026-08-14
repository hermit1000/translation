import re
import json
import logging
from pathlib import Path
from typing import Dict, Tuple, Union
from module.content import Content
from module.font_table import FontTable
from module.decoding import decode, encode

logger = logging.getLogger(__name__)


def write_code(data: bytearray, hex_start: str, hex_end: str, code_hex: str, count: int) -> bytearray:
    spos = int(hex_start, 16)
    epos = int(hex_end, 16)
    pos = spos

    for i in range(count):
        if pos >= epos:
            break

        code_int = int(code_hex, 16)
        code_int += i
        code1 = (code_int & 0xFF00) >> 8
        code2 = code_int & 0x00FF
        data[pos] = code1
        data[pos + 1] = code2
        pos += 2

    return data


def write_code_1byte(data: bytearray, hex_start: str, hex_end: str, code_hex: str, count: int) -> bytearray:
    spos = int(hex_start, 16)
    epos = int(hex_end, 16)
    pos = spos

    for i in range(count):
        if pos >= epos:
            break

        code_int = int(code_hex, 16)
        code_int += i
        data[pos] = code_int
        pos += 1

    return data


class Script:
    def __init__(self, file_path: str = "") -> None:
        raw_script = dict()

        # Read a script if the file path is specified
        if len(file_path):
            if Path(file_path).exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_script = json.load(f)
            else:
                raise FileNotFoundError(f"{file_path} does not exist.")

        self.zero_padding = raw_script.pop("zero_padding", None)
        self.encoding = raw_script.pop("encoding", None)
        self.custom_input = raw_script.pop("custom_input", None)
        self.binary_input = raw_script.pop("binary_input", None)
        self.script: Dict[str, Content] = {
            address: Content.parse(sentence) for address, sentence in raw_script.items()
        }

    def apply_zero_padding(self, data: bytearray) -> bytearray:
        """Apply zero padding to the binary data
        Args:
            data (bytearray): A binary data.
        Returns:
            bytearray: A binary data with zero padding.
        """
        if self.zero_padding is None:
            return data

        start_address, length = self.zero_padding.split(":")
        start_address = int(start_address, 16)
        length = int(length, 16)

        null_bytes_to_insert = bytearray([0] * length)
        try:
            data[start_address:start_address] = null_bytes_to_insert
            print("Insertion successful!")
            print(f"Original data length: {len(data) - length:X}")
            print(f"Data length after insertion: {len(data)}")
            print(f"Null bytes inserted in range: {start_address:X} to {start_address + length - 1:X}")

        except IndexError:
            print(f"Error: Start address({start_address:X}) is out of data range.")

        except Exception as e:
            print(f"Unknown error occurred: {e}")

        return data

    def set_address_padding(self, address_padding: int = 5) -> None:
        """Set address padding
        Args:
            address_padding (int): A padding length of address.
        """
        annoying = []
        for address in self.script.keys():
            start, end = address.split("=")
            if len(start) != address_padding:
                annoying.append(address)
                continue
            if len(end) != address_padding:
                annoying.append(address)
                continue

        for address in annoying:
            sentence = self.script.pop(address)
            start, end = address.split("=")
            start_int = int(start, 16)
            end_int = int(end, 16)
            new_address = f"{start_int:0{address_padding}X}={end_int:0{address_padding}X}"
            self.script[new_address] = sentence

    def save(self, file_path: str, address_padding: int = 5) -> None:
        """Save the script to a file
        Args:
            file_path (str): A path to a file.
        """
        save_dict = dict()

        # Set zero padding
        if self.zero_padding is not None:
            save_dict["zero_padding"] = self.zero_padding

        # Set encoding
        if self.encoding is not None:
            save_dict["encoding"] = self.encoding

        # Set custom input
        if self.custom_input is not None:
            save_dict["custom_input"] = self.custom_input

        # Set binary input
        if self.binary_input is not None:
            save_dict["binary_input"] = self.binary_input

        # Set address padding
        self.set_address_padding(address_padding)

        # Sort by keys (address) for the main script
        self.script = dict(sorted(self.script.items()))

        save_dict.update({address: content.serialize() for address, content in self.script.items()})
        with open(file_path, "w", encoding="utf-8", newline="\r\n") as f:
            json.dump(save_dict, f, ensure_ascii=False, indent=4)

    def add_script(self, script: Dict[str, Union[str, Content]]) -> None:
        """Add a script to the main script
        Args:
            script (Dict): A script.
        """
        self.script.update({address: Content.parse(sentence) for address, sentence in script.items()})

    def validate(self, font_table: FontTable) -> Tuple[int, int]:
        """Check the script
        Args:
            font_table (FontTable): A font table.
        Returns:
            Tuple[int, int]: count of false length, count of false characters
        """
        # Check script
        count_false_length = 0
        count_false_characters = 0

        for address, content in self.script.items():
            if "=" not in address:
                continue
            length_from_address = font_table.check_length_from_address(address)
            length_from_sentence = font_table.check_length_from_sentence(content.text)
            if length_from_address != length_from_sentence:
                print(f"Wrong sentence length:{address}: {length_from_address}-{length_from_sentence}")
                count_false_length += 1

            # Check if there is false characters in a sentence via comparison with the font table
            count_false_character, false_character = font_table.verify_sentence(content.text)
            if count_false_character:
                print(f"Wrong letters:{address}: {count_false_character}-{false_character}")
                count_false_characters += count_false_character

        return count_false_length, count_false_characters

    def diff_addresses(self, dst_script: Dict) -> int:
        """
        Compare the address of two scripts

        Parameters:
            dst_script (Dict): The script to check.

        Returns:
            int: The number of differences between the two scripts.
        """
        reversed = False
        if len(self.script.keys()) >= len(dst_script):
            scripts_1 = self.script
            scripts_2 = dst_script
        else:
            scripts_1 = dst_script
            scripts_2 = self.script
            reversed = True

        count_diff = 0
        for key, _ in scripts_1.items():
            if scripts_2.get(key) is None:
                if reversed:
                    print(f"Diff = src address [], dst address [{key}]")
                else:
                    print(f"Diff = src address [{key}], dst address []")
                count_diff += 1

        print(f"Number of diff = {count_diff}")
        return count_diff

    def validate_with_binary(
        self,
        font_table: FontTable,
        binary_data=None,
        binary_path: Path = None,
        custom_words: Dict = None,
    ) -> bool:
        """Check the script with a binary data
        Args:
            binary_path (Path): A binary data path.
        Returns:
            bool: True if the script is not valid.
        """
        if binary_data is None:
            # Read a binary data
            if not Path(binary_path).exists():
                print(f"{binary_path} does not exist.")
                return
            with open(binary_path, "rb") as f:
                binary_data = f.read()
            binary_data = bytearray(binary_data)

        # Decoding bianry data
        if self.encoding is not None:
            binary_data = decode(binary_data, self.encoding)

        diff_status = False
        err_reason = ""
        for address, content in self.script.items():
            if "=" not in address:
                continue

            spos = int(address.split("=")[0], 16)

            is_diff = False

            if content.is_hex:
                codes = content.hex_codes
                length = len(codes) // 2
                for i in range(length):
                    code_int = int(codes[i * 2 : i * 2 + 2], 16)
                    if code_int != binary_data[spos + i]:
                        is_diff = True
                        err_reason = f"{code_int:02X}/{binary_data[spos + i]:02x}"
                        break
            else:
                idx = 0
                parts = re.split(r"\{([^}]+)\}", content.text)
                is_word = False
                for part in parts:
                    if not part:
                        is_word = not is_word
                        continue

                    if is_word:
                        if custom_words is None or part not in custom_words:
                            raise ValueError(f"Custom word '{part}' not found in custom_words for address {address}")
                        code_hex = custom_words[part]
                        length = len(code_hex) // 2
                        code_bin_hex = bytes(binary_data[spos + idx : spos + idx + length]).hex().upper()
                        if code_hex.upper() != code_bin_hex:
                            is_diff = True
                            err_reason = f"{code_hex}/{code_bin_hex}"
                            break
                        idx += length
                    else:
                        idx_char = 0
                        while idx_char < len(part):
                            letter = part[idx_char]
                            if letter == "|":
                                idx_char += 1
                                if idx_char >= len(part):
                                    break
                                letter = part[idx_char]
                                code_hex = font_table.get_code_ascii(letter)
                                code_bin_int = binary_data[spos + idx]
                                code_bin_hex = f"{code_bin_int:02X}"
                                if code_hex != code_bin_hex:
                                    is_diff = True
                                    err_reason = f"{code_hex}/{code_bin_hex}"
                                    break
                                idx += 1
                            else:
                                code_hex = font_table.get_code(letter)
                                code_bin_int = (binary_data[spos + idx] << 8) + binary_data[spos + idx + 1]
                                code_bin_hex = f"{code_bin_int:04X}"
                                if code_hex != code_bin_hex:
                                    is_diff = True
                                    err_reason = f"{code_hex}/{code_bin_hex}"
                                    break
                                idx += 2
                            idx_char += 1
                        if is_diff:
                            break
                    is_word = not is_word
            if is_diff:
                print(f"{address}:{content.text} - {err_reason}")

                diff_status = True
        return diff_status

    def filter_sentences(self) -> bool:
        """
        To get rid of 1-byte noisy characters
        """

        remove_key_list = []
        modified_script = dict()

        for address, content in self.script.items():
            if "=" not in address:
                continue
            if "|" not in content.text:
                continue

            start, end = address.split("=")
            start = int(start, 16)  # Convert to integer
            end = int(end, 16)  # Convert to integer

            is_1byte = False
            remove = ""
            add_byte = 0
            for character in content.text:
                if character == "|":
                    is_1byte = True
                    continue

                if is_1byte:
                    if character == "C":
                        is_1byte = False
                        break
                    else:
                        remove += f"|{character}"
                        add_byte += 1
                        is_1byte = False
                else:
                    break

            if add_byte > 0:
                remove_key_list.append(address)
                start_new = start + add_byte
                if start_new >= end:
                    continue
                address_new = f"{start_new:05X}={end:05X}"
                content.text = content.text[add_byte * 2 :]
                modified_script[address_new] = content

        if len(remove_key_list) == 0:
            print("No sentences are connected.")
            return False

        # Remove old sentences
        for key in remove_key_list:
            del self.script[key]

        # Update script
        self.script.update(modified_script)
        self.script = dict(sorted(self.script.items()))

        return True

    def filter_given_sentence(self, given_sentence: str) -> bool:
        """
        To get rid of a given sentence
        """
        remove_key_list = []
        given_text = Content.parse(given_sentence).text
        for address, content in self.script.items():
            if content.text != given_text:
                continue
            remove_key_list.append(address)

        if len(remove_key_list) == 0:
            print("No sentences are removed.")
            return False

        # Remove old sentences
        for key in remove_key_list:
            del self.script[key]

        return True

    def replace_sentence(self, address: str, new_address: str, sentence: Union[str, Content]):
        if address not in self.script.keys():
            print(f"{address} is not in the script.")
            return

        old_content = self.script[address]
        new_content = Content.parse(sentence)
        if new_content.description is None:
            new_content.description = old_content.description
        if address == new_address and len(old_content.text) == len(new_content.text):
            self.script[address] = new_content
        else:
            del self.script[address]
            self.script[new_address] = new_content
            self.script = dict(sorted(self.script.items()))

    def extract_script(
        self,
        data: bytearray,
        font_table: FontTable,
        length_threshold: int,
        check_ascii: bool = False,
        check_ascii_restriction: bool = False,
        check_range: bool = False,
    ) -> Dict:
        """Extract a script from a binary data
        Args:
            data (bytearray): A binary data.
            font_table (FontTable): A font table.
            length_threshold (int): A threshold of the length of a sentence.
            check_ascii (bool): If True, check if the sentence contains only ASCII characters.
            check_ascii_restriction (bool): If True, check if the sentence contains only ASCII characters and the first character is not '_'.
            check_range (bool): If True, check if the sentence contains only characters in the font table.
        Returns:
            Dict: A dictionary of a script log.
        """

        i = 0
        length = 0  # Sentence length in bytes
        sentence = ""
        sentence_log = ""
        self.script = dict()
        script_log = dict()

        while i < len(data) - 1:
            # Extract a 2byte code
            code_int = (data[i] << 8) + data[i + 1]
            code_hex = f"{code_int:X}"

            need_to_stop = True

            character = font_table.get_char(code_hex)
            if character is not None:
                need_to_stop = False

            if check_range and font_table.range(code_int):
                need_to_stop = False

            if not need_to_stop:
                # Find a character in the font table
                character = font_table.get_char(code_hex)

                if character:  # Character is in the font table
                    sentence += character
                    if character == "■":
                        sentence_log += f":{code_hex}" if sentence_log else f"{code_hex}"
                    length += 2
                    i += 2
                else:
                    sentence += "@"
                    sentence_log += f":@{code_hex}" if sentence_log else f"@{code_hex}"
                    length += 2
                    i += 2
            else:
                if check_ascii:
                    code_int = data[i]
                    code_hex = f"{code_int:02X}"
                    character = font_table.get_char_ascii(code_hex)

                    if check_ascii_restriction and character != "_" and length == 0:
                        need_to_stop = True
                    elif character is not None:
                        sentence += "|" + character
                        length += 1
                        need_to_stop = False

                # Check sentence length and save
                if need_to_stop:
                    if length >= length_threshold:
                        if "�" not in sentence:  # Need to check this later
                            address = f"{i - length:05X}={i - 1:05X}"
                            self.script[address] = Content(text=sentence)
                            if sentence_log:
                                script_log[address] = sentence_log
                    sentence = ""
                    sentence_log = ""
                    length = 0
                i += 1

        # Check a result of the end of data
        if length >= length_threshold:
            address = f"{i - length:05X}={i - 1:05X}"
            self.script[address] = Content(text=sentence)
            if sentence_log:
                script_log[address] = sentence_log
            sentence = ""
            sentence_log = ""
            length = 0

        return script_log

    def write_script(
        self, data: bytearray, font_table: FontTable, custom_words: Dict = None, binary_input_dir: Path = None
    ) -> Tuple[bytearray, int]:
        valid_sentence_count = 0

        # Check if decoding is needed
        if self.encoding is not None:
            data = decode(data, self.encoding)

        # Check if custom inputs exist
        if self.custom_input is not None:
            for address, codes in self.custom_input.items():
                [code_hex_start, code_hex_end] = address.split("=")
                spos = int(code_hex_start, 16)
                epos = int(code_hex_end, 16)

                content = Content.parse(codes)
                codes = content.hex_codes if content.is_hex else content.text

                # Check if the format is right
                num_codes = epos - spos + 1
                if len(codes) != num_codes * 2:
                    raise ValueError(
                        f"The length of custom input is not matched. {address}:{len(codes)} != {num_codes}"
                    )

                for i in range(num_codes):
                    code_int = int(codes[i * 2 : i * 2 + 2], 16)
                    data[spos + i] = code_int

        if self.binary_input is not None and binary_input_dir is not None and binary_input_dir.exists():
            for address, desc in self.binary_input.items():
                [code_hex_start, code_hex_end] = address.split("=")
                spos = int(code_hex_start, 16)
                epos = int(code_hex_end, 16)

                file_name = Content.parse(desc).text

                file_path = binary_input_dir / file_name
                if not file_path.exists():
                    logger.warning(f"{file_path.name} does not exist.")
                    continue
                with open(file_path, "rb") as f:
                    binary_data = f.read()
                binary_data = bytearray(binary_data)

                # Check if the format is right
                num_codes = epos - spos + 1
                if len(binary_data) != num_codes:
                    raise ValueError(
                        f"The length of binary input is not matched. {address}:{len(binary_data)} != {num_codes}"
                    )
                data[spos : epos + 1] = binary_data

        # Write scripts
        for address, content in self.script.items():
            # Check if there is a unsupported address format
            if "=" not in address:
                assert 0, f"{address} is not in the correct format."

            [code_hex_start, code_hex_end] = address.split("=")
            spos = int(code_hex_start, 16)
            epos = int(code_hex_end, 16)
            pos = spos

            sentence_text = content.text
            if content.is_hex:
                codes = content.hex_codes

                # Check if the format is right
                num_codes = epos - spos + 1
                if len(codes) != num_codes * 2:
                    assert 0, f"The length of custom input is not matched. {address}:{len(codes)} != {num_codes}"

                for i in range(num_codes):
                    code_int = int(codes[i * 2 : i * 2 + 2], 16)
                    data[spos + i] = code_int

                valid_sentence_count += 1
                continue

            # Check if there is a unsupported letter in the sentence
            skip_sentence = False
            check_1byte = False
            check_brace = False
            for character in sentence_text:
                if check_brace:
                    if character == "}":
                        check_brace = False
                    continue
                if character == "{":
                    check_brace = True
                    continue
                if character == "|":
                    check_1byte = True
                    continue
                if check_1byte:
                    if not font_table.exists_1byte(character):
                        skip_sentence = True
                        break

                    code = font_table.get_code_ascii(character)
                    if character in ["･", "¥"]:  # 1byte Japanese character
                        pass
                    elif int(code, 16) > 0xA3 and int(code, 16) < 0xF0:  # 1byte Japanese character
                        skip_sentence = True
                        break
                    check_1byte = False
                    continue
                if character == "@":  # an ignore character
                    continue
                if not font_table.exists(character):
                    skip_sentence = True
                    break

                if font_table.is_japanese(character):
                    skip_sentence = True
                    break
            if skip_sentence:
                continue
            valid_sentence_count += 1

            # Write characters in the sentence
            parts = re.split(r"\{([^}]+)\}", sentence_text)
            is_word = False
            for part in parts:
                if not part:
                    is_word = not is_word
                    continue

                if is_word:
                    if custom_words and part in custom_words:
                        hex_value = custom_words[part]
                        num_bytes = len(hex_value) // 2
                        for i in range(num_bytes):
                            byte_str = hex_value[i * 2 : i * 2 + 2]
                            if pos + i >= len(data):
                                break
                            data[pos + i] = int(byte_str, 16)
                        pos += num_bytes
                    else:
                        raise ValueError(f"Custom word '{part}' not found in custom_words for address {address}")
                else:
                    idx_char = 0
                    while idx_char < len(part):
                        character = part[idx_char]
                        if character == "|":
                            idx_char += 1
                            if idx_char < len(part):
                                character = part[idx_char]
                                if font_table.get_code_ascii(character) is not None:
                                    code_hex = font_table.get_code_ascii(character)
                                    data[pos] = int(code_hex, 16)
                                else:
                                    assert 0, f"{code_hex_start}:{character} is not in the 1-byte font table."
                                pos += 1
                        elif character in ["@"]:
                            pos += 2
                        else:
                            if font_table.get_code(character) is not None:
                                code_hex = font_table.get_code(character)
                                code_int = int(code_hex, 16)
                                data[pos] = (code_int & 0xFF00) >> 8
                                data[pos + 1] = code_int & 0x00FF
                            else:
                                assert 0, f"{character} is not in the 2-byte font table. - {address}:{sentence_text}"
                            pos += 2
                        idx_char += 1
                is_word = not is_word

        # Check if encoding is needed
        if self.encoding is not None:
            data = encode(data, self.encoding)

        return data, valid_sentence_count
