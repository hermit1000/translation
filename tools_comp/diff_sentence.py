import json
from pathlib import Path


def check_length_from_address(address: str) -> int:
    [code_hex_start, code_hex_end] = address.split("=")
    length_from_address = int(code_hex_end, 16) - int(code_hex_start, 16) + 1
    return length_from_address


def check_length_from_sentence(sentence: str) -> int:
    sentence = sentence.split("#")[0]
    # Check if the sentence is hex-only
    if "0x:" == sentence[:3]:
        sentence = sentence[3:]  # Remove the hex-only code prefix
        return len(sentence) // 2

    total_length = 0
    i = 0
    while i < len(sentence):
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


def diff_addresses(src_script: dict, dst_script: dict) -> int:
    """
    Compare the address of two scripts

    Parameters:
        dst_script (Dict): The script to check.

    Returns:
        int: The number of differences between the two scripts.
    """
    reversed = False
    if len(src_script.keys()) >= len(dst_script):
        scripts_1 = src_script
        scripts_2 = dst_script
    else:
        scripts_1 = dst_script
        scripts_2 = src_script
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


def find_diff(script_dir: Path):
    for file in script_dir.rglob("*.json"):  # Use rglob to search subdirectories
        if "_jpn.json" not in file.name:
            continue

        # if "OPEN" not in file.name:
        #     continue

        dst_path = file.parent / file.name.replace("_jpn.json", "_kor.json")
        if not dst_path.exists():
            continue

        error_found = False

        file_tag = f"{file.parent.name}/{file.name}"
        print(file_tag)
        with open(file, "r", encoding="utf-8") as f:
            src = json.load(f)
        with open(dst_path, "r", encoding="utf-8") as f:
            dst = json.load(f)

        # Check addresses in the source script
        count_diff = diff_addresses(src, dst)
        if count_diff:
            print(f"Addresses are different in {file_tag}")
            return

        # Check address
        for address, src_sentence in src.items():
            if "=" not in address:
                continue
            # Check if the address is in the destination script
            if address not in dst:
                continue

            # Check if the src and dst sentences are valid
            length = check_length_from_address(address)
            length_from_src_sentence = check_length_from_sentence(sentence=src_sentence)

            if length != length_from_src_sentence:
                # assert 0, f"Jpn sentence length is not matched. {address}:{length} != {length_from_src_sentence}"
                print(f"Jpn sentence length is not matched. {address}:{length} != {length_from_src_sentence}")
                error_found = True
                continue

            # Check if the src and dst sentences are valid
            dst_sentence = dst[address]
            length_from_dst_sentence = check_length_from_sentence(sentence=dst_sentence)
            if length != length_from_dst_sentence:
                print(f"Kor sentence length is not matched. {address}:{length} != {length_from_dst_sentence}")
                # assert 0, f"Kor sentence length is not matched. {address}:{length} != {length_from_dst_sentence}"
                error_found = True
                continue

        if error_found:
            break


if __name__ == "__main__":
    base_dir = Path("c:/work_han/workspace6")
    script_dir = base_dir / "script-pc98"

    find_diff(script_dir)
