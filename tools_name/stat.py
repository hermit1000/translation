from module.name_db import NameDB


def main():
    name_db = NameDB()
    query = {"game": ["nb2"]}
    print(f"{name_db.check_number(query)} - 노부나가의 야망 2")
    query = {"game": ["nb3"]}
    print(f"{name_db.check_number(query)} - 노부나가의 야망 3")
    query = {"game": ["nb4"]}
    print(f"{name_db.check_number(query)} - 노부나가의 야망 4")
    query = {"game": ["nb5"]}
    print(f"{name_db.check_number(query)} - 노부나가의 야망 5")
    query = {"game": ["taiko1"]}
    print(f"{name_db.check_number(query)} - 태합입지전 1")
    query = {"game": ["taiko2"]}
    print(f"{name_db.check_number(query)} - 태합입지전 2")
    print(f"{name_db.check_number()} - Total")
    # name_db.print_duplicate()
    # name_db.save_db()


if __name__ == "__main__":
    main()
