from pathlib import Path
from module.script import Script


def check_length_from_sentence(sentence: str) -> int:
    sentence = sentence.split("#")[0]
    # Check if the sentence is hex-only
    if "0x:" == sentence[:3]:
        sentence = sentence[3:]  # Remove the hex-only code prefix
        return len(sentence) // 2

    num_one_byte = sentence.count("|")
    num_two_byte = len(sentence) - num_one_byte * 2
    length_from_sentence = num_one_byte + num_two_byte * 2
    return length_from_sentence


def main():
    base_dir = Path("c:/work_han/workspace/script-dos")

    jpn_script_path = base_dir / "MAIN.EXE_jpn.json"
    kor_script_path = base_dir / "MAIN.EXE_kor.json"
    jpn_script = Script(str(jpn_script_path))
    kor_script = Script(str(kor_script_path))

    count = 0
    for kor_address, kor_content in kor_script.script.items():
        kor_sentence = kor_content.text
        start, end = kor_address.split("=")
        start = int(start, 16)
        end = int(end, 16)
        address_len = end - start + 1

        if start < 0x436C0:
            continue
        if start > 0x442F5:
            continue

        for jpn_address, jpn_content in jpn_script.script.items():
            jpn_sentence = jpn_content.text
            start_jpn, end_jpn = jpn_address.split("=")
            start_jpn = int(start_jpn, 16)
            end_jpn = int(end_jpn, 16)
            address_len_jpn = end_jpn - start_jpn + 1

            if start_jpn != start:
                continue

            if address_len_jpn != address_len:
                print(start)
            if address_len_jpn != check_length_from_sentence(jpn_sentence):
                print(address_len_jpn - check_length_from_sentence(jpn_sentence))
                print(start)
            if check_length_from_sentence(kor_sentence) < check_length_from_sentence(jpn_sentence):
                print(start)
            if check_length_from_sentence(kor_sentence) == check_length_from_sentence(jpn_sentence):
                continue

            print(check_length_from_sentence(kor_sentence) - check_length_from_sentence(jpn_sentence))

            count += 1

    print(count)


if __name__ == "__main__":
    main()
