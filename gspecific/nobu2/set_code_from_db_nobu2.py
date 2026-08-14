from module.name_db import NameDB
from module.name_codec import (
    align_encoded_length,
    clean_script_name,
    format_korean_name_without_added_space,
)
from module.script import Script


FILE_CONFIG = {
    "DATA17.DAT": {
        "start": 0x01714,
        "end": 0x01945,
        "name_count": 17,
    },
    "DATA50.DAT": {
        "start": 0x01714,
        "end": 0x019F9,
        "name_count": 53,
    },
    "ODAMAIN.EXE": {
        "start": 0x17724,
        "end": 0x17A09,
        "name_count": 53,
    },
}


def read_name_arrays(script_jpn: Script, file_name: str, file_config=None):
    if file_config is None:
        file_config = FILE_CONFIG
    config = file_config[file_name]
    entries = []

    for address, content in script_jpn.script.items():
        if "=" not in address:
            continue
        start = int(address.split("=", 1)[0], 16)
        if config["start"] <= start <= config["end"]:
            entries.append((address, content.text))

    entries.sort(key=lambda item: int(item[0].split("=", 1)[0], 16))

    name_count = config["name_count"]
    expected_count = name_count * 2
    if len(entries) != expected_count:
        raise ValueError(
            f"{file_name}: expected {expected_count} name entries "
            f"({name_count} family + {name_count} given), got {len(entries)}"
        )

    return entries[:name_count], entries[name_count:]


def make_modification(address: str, length: int, sentence: str):
    start = int(address.split("=", 1)[0], 16)
    new_address = f"{start:05X}={start + length - 1:05X}"
    return address, new_address, sentence


def calculate_modifications(
    script_jpn: Script,
    file_name: str,
    name_db: NameDB,
    game: str,
    file_config=None,
):
    family_names, given_names = read_name_arrays(script_jpn, file_name, file_config)
    mod_list_jpn = []
    mod_list_kor = []
    unknown_names = []

    for (fn_address, fn_jpn_raw), (gn_address, gn_jpn_raw) in zip(family_names, given_names):
        fn_jpn = clean_script_name(fn_jpn_raw)
        gn_jpn = clean_script_name(gn_jpn_raw)
        full_name_jpn = f"{fn_jpn} {gn_jpn}"

        korean_name = name_db.get_korean_name(full_name_jpn, game)
        if korean_name is None:
            unknown_names.append(full_name_jpn)
            continue

        fn_kor, gn_kor = korean_name.family, korean_name.given
        fn_jpn_len = len(fn_jpn) * 2
        gn_jpn_len = len(gn_jpn) * 2
        fn_kor, gn_kor, fn_kor_len, gn_kor_len = format_korean_name_without_added_space(fn_kor, gn_kor)

        fn_length, fn_jpn, fn_kor = align_encoded_length(fn_jpn, fn_kor, fn_jpn_len, fn_kor_len)
        gn_length, gn_jpn, gn_kor = align_encoded_length(gn_jpn, gn_kor, gn_jpn_len, gn_kor_len)

        mod_list_jpn.append(make_modification(fn_address, fn_length, fn_jpn))
        mod_list_kor.append(make_modification(fn_address, fn_length, fn_kor))
        mod_list_jpn.append(make_modification(gn_address, gn_length, gn_jpn))
        mod_list_kor.append(make_modification(gn_address, gn_length, gn_kor))

    return mod_list_jpn, mod_list_kor, unknown_names


def print_modifications(
    file_name: str,
    mod_list_jpn: list,
    mod_list_kor: list,
    unknown_names: list,
    file_config=None,
):
    if file_config is None:
        file_config = FILE_CONFIG
    name_count = file_config[file_name]["name_count"]
    converted_count = len(mod_list_jpn) // 2
    print(f"\n[{file_name}] {converted_count}/{name_count} names converted, {len(unknown_names)} unknown")

    for index, (jpn_info, kor_info) in enumerate(zip(mod_list_jpn, mod_list_kor)):
        name_part = "family" if index % 2 == 0 else "given "
        address, address_new, jpn = jpn_info
        _, kor_address_new, kor = kor_info
        print(f"{name_part} JPN {address} -> {address_new}: {jpn}")
        print(f"{name_part} KOR {address} -> {kor_address_new}: {kor}")

    for full_name in unknown_names:
        print(f"unknown: {full_name}")


def save_modifications(
    script_jpn: Script,
    script_kor: Script,
    jpn_path: str,
    kor_path: str,
    mod_list_jpn: list,
    mod_list_kor: list,
):
    for address, address_new, sentence in mod_list_jpn:
        script_jpn.replace_sentence(address, address_new, sentence)
    for address, address_new, sentence in mod_list_kor:
        script_kor.replace_sentence(address, address_new, sentence)

    script_jpn.save(jpn_path)
    script_kor.save(kor_path)


def main():
    ws_num = 0
    base_dir = f"c:/work_han/workspace{ws_num}/script-pc98"
    save = False
    name_db = NameDB()
    game = "nb2"

    for file_name in FILE_CONFIG:
        jpn_path = f"{base_dir}/{file_name}_jpn.json"
        kor_path = f"{base_dir}/{file_name}_kor.json"
        script_jpn = Script(jpn_path)
        script_kor = Script(kor_path)

        mod_list_jpn, mod_list_kor, unknown_names = calculate_modifications(script_jpn, file_name, name_db, game)
        print_modifications(file_name, mod_list_jpn, mod_list_kor, unknown_names)

        if save:
            save_modifications(
                script_jpn,
                script_kor,
                jpn_path,
                kor_path,
                mod_list_jpn,
                mod_list_kor,
            )


if __name__ == "__main__":
    main()
