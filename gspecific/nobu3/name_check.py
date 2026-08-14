from module.name_db import NameDB
from module.script import Script
from rich.console import Console


def main():
    console = Console()
    name_db = NameDB()
    game = "nb5"
    ws_num = 5
    base_dir = f"c:/work_han/workspace{ws_num}/script-pc98"

    file_name = "S0T.NB5"
    # file_name = "MAIN.EXE"
    # file_name = "SNDATA1.CIM"
    script_jpn = Script(f"{base_dir}/{file_name}_jpn.json")
    script_kor = Script(f"{base_dir}/{file_name}_kor.json")

    fn_jpn = ""
    fn_kor = ""
    gn_jpn = ""
    gn_kor = ""
    prev_address = ""

    mod_list = []

    for address, content in script_jpn.script.items():
        sentence = content.text
        start, end = address.split("=")
        start = int(start, 16)
        end = int(end, 16)
        # if start < 0x1192:
        #     continue
        # if start < 0x3F964:
        #     continue
        # if start > 0x41984:
        #     continue

        if game == "nb3":
            if file_name in ["SNDATA1.CIM", "SNDATA2.CIM"]:
                if start < 0xD38:
                    continue
            if file_name == "MAIN.EXE":
                if start < 0x24C6A:
                    continue
                if start > 0x26FED:
                    continue

        if len(fn_jpn) == 0:
            fn_jpn = sentence
            fn_kor = script_kor.script[address].text
            prev_address = address
            continue

        if len(gn_jpn) == 0:
            gn_jpn = sentence
            gn_kor = script_kor.script[address].text

        fn_jpn = fn_jpn.replace("␀", "")
        gn_jpn = gn_jpn.replace("␀", "")

        if "0x:" in fn_jpn:
            fn_jpn = name_db.get_name_from_code("family", fn_jpn, game)
        if "0x:" in gn_jpn:
            gn_jpn = name_db.get_name_from_code("given", gn_jpn, game)

        full_name_jpn_clean = f"{fn_jpn} {gn_jpn}"

        name_info = name_db.get_full_name(full_name_jpn_clean)
        if name_info is None:
            db = name_db.family_name_db.get(fn_jpn)
            db_fn_kor = "?" if db is None else db.get("kor", "?")
            db = name_db.given_name_db.get(gn_jpn)
            db_gn_kor = "?" if db is None else db.get("kor", "?")

            console.print(f"{full_name_jpn_clean} - {db_fn_kor} {db_gn_kor}")

            if db_fn_kor == "?":
                kor = name_db.given_name_db.get(fn_jpn, "?")
                if kor != "?":
                    console.print("Warning: Family name is in the given name database.")
            if db_gn_kor == "?":
                kor = name_db.family_name_db.get(gn_jpn, "?")
                if kor != "?":
                    console.print("Warning: Given name is in the family name database.")

            _, prior = prev_address.split("=")
            post, _ = address.split("=")
            prior = int(prior, 16)
            post = int(post, 16)
            if post - prior > 8:
                print(f"Address mismatch: {prev_address}:{post - prior}")
                break
            fn_jpn = ""
            gn_jpn = ""
            continue
        else:
            if name_db.add_game(full_name_jpn_clean, game):
                print(full_name_jpn_clean)

        korean_name = name_db.get_korean_name(full_name_jpn_clean)
        db_fn_kor, db_gn_kor = korean_name.family, korean_name.given

        # Check for debugging
        # if len(gn_kor) > 3 and gn_jpn != gn_kor:
        #     print(f"{full_name_jpn_clean}:{gn_jpn} - {address}")
        # if len(fn_kor) > 3 and fn_jpn != fn_kor:
        #     print(f"{full_name_jpn_clean}:{fn_jpn} - {address}")

        if len(db_gn_kor) < 4 and db_gn_kor != gn_kor:
            info_str = f"{address},{gn_jpn},{db_gn_kor}"
            mod_list.append(info_str)
            print(info_str)

        if len(db_fn_kor) < 4 and db_fn_kor != fn_kor:
            info_str = f"{prev_address},{fn_jpn},{db_fn_kor}"
            mod_list.append(info_str)
            print(info_str)

        fn_jpn = ""
        gn_jpn = ""

    for info_str in mod_list:
        address, jpn, kor = info_str.split(",")

        start, end = address.split("=")
        start = int(start, 16)
        end = int(end, 16)

        diff = len(kor) - len(jpn)

        if diff > 0:
            end += diff * 2
            jpn += "␀" * diff

        script_jpn.replace_sentence(address, f"{start:05X}={end:05X}", jpn)
        script_kor.replace_sentence(address, f"{start:05X}={end:05X}", kor)

    # script_jpn.save(f"{base_dir}/{file_name}_jpn.json")
    # script_kor.save(f"{base_dir}/{file_name}_kor.json")
    # name_db.save_db()


if __name__ == "__main__":
    main()
