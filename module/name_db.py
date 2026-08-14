import json
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple, Union

from .name_codec import NamePair


Translation = Union[str, List[str]]


def read_name_db(name_db_path: Path) -> dict:
    if not name_db_path.exists():
        return {}
    with open(name_db_path, "r", encoding="utf-8") as f:
        return json.load(f)


class NameDB:
    def __init__(self, db_dir: Optional[Path] = None) -> None:
        self.db_dir = Path(db_dir) if db_dir is not None else Path(__file__).resolve().parent.parent / "name_db"
        self.full_name_db = {}
        self.family_name_db = {}
        self.given_name_db = {}
        self._code_index: Dict[Tuple[str, str, str], str] = {}
        self.read_db()

    def read_db(self) -> None:
        self.full_name_db = read_name_db(self.db_dir / "full_name_db.json")
        self.family_name_db = read_name_db(self.db_dir / "family_name_db.json")
        self.given_name_db = read_name_db(self.db_dir / "given_name_db.json")
        self._build_code_index()

    def _build_code_index(self) -> None:
        self._code_index = {}
        for name_type, database in (("family", self.family_name_db), ("given", self.given_name_db)):
            for name, info in database.items():
                for game, code in info.get("code", {}).items():
                    self._code_index[(name_type, game, code)] = name

    def save_db(self) -> None:
        for info in self.full_name_db.values():
            if len(info.get("game", [])) > 1:
                info["game"].sort()

        self.full_name_db = dict(sorted(self.full_name_db.items()))
        self.family_name_db = dict(sorted(self.family_name_db.items()))
        self.given_name_db = dict(sorted(self.given_name_db.items()))

        self.db_dir.mkdir(parents=True, exist_ok=True)
        for file_name, database in (
            ("full_name_db.json", self.full_name_db),
            ("family_name_db.json", self.family_name_db),
            ("given_name_db.json", self.given_name_db),
        ):
            with open(self.db_dir / file_name, "w", encoding="utf-8", newline="\r\n") as f:
                json.dump(database, f, ensure_ascii=False, indent=4)

    def iter_full_names(self, game: Optional[str] = None) -> Iterator[Tuple[str, dict]]:
        for full_name, info in self.full_name_db.items():
            if game is not None and game not in info.get("game", []):
                continue
            yield full_name, info

    def iter_name_pairs(self, game: Optional[str] = None) -> Iterator[Tuple[NamePair, NamePair, dict]]:
        for full_name, info in self.iter_full_names(game):
            yield NamePair.parse(full_name), NamePair.parse(info["kor"]), info

    def get_full_name(self, full_name: str, game: Optional[str] = None) -> Optional[dict]:
        info = self.full_name_db.get(full_name)
        if info is None:
            return None
        if game is not None and game not in info.get("game", []):
            return None
        return info

    def get_korean_name(self, full_name: str, game: Optional[str] = None) -> Optional[NamePair]:
        info = self.get_full_name(full_name, game)
        if info is None:
            return None
        return NamePair.parse(info["kor"])

    def add_game(self, full_name: str, game: str) -> bool:
        info = self.full_name_db.get(full_name)
        if info is None:
            raise KeyError(full_name)
        games = info.setdefault("game", [])
        if game in games:
            return False
        games.append(game)
        return True

    def find_name_by_code(self, name_type: str, code: str, game: str) -> Optional[str]:
        if name_type not in {"family", "given"}:
            raise ValueError("name_type must be 'family' or 'given'.")
        return self._code_index.get((name_type, game, code.removeprefix("0x:")))

    def get_name_from_code(self, name_type: str, code: str, game: str) -> str:
        return self.find_name_by_code(name_type, code, game) or code

    def check_full_name_exist(self, full_name: str) -> bool:
        return full_name in self.full_name_db

    def check_family_name_exist(self, family_name: str) -> bool:
        return family_name in self.family_name_db

    def check_given_name_exist(self, given_name: str) -> bool:
        return given_name in self.given_name_db

    def check_number(self, query: Optional[dict] = None, unique: bool = False) -> int:
        games = (query or {}).get("game")
        count = 0
        for _, info in self.iter_full_names():
            entry_games = info.get("game", [])
            if games is not None and any(game not in entry_games for game in games):
                continue
            if not unique or len(entry_games) == 1:
                count += 1
        return count

    def validate(self) -> List[str]:
        errors = []
        for full_name, info in self.full_name_db.items():
            try:
                japanese = NamePair.parse(full_name)
                component_translation = info.get("desc", {}).get("kor_org", info["kor"])
                korean = NamePair.parse(component_translation)
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"{full_name}: {exc}")
                continue

            if not isinstance(info.get("game"), list) or not info["game"]:
                errors.append(f"{full_name}: game must be a non-empty list")

            self._validate_component(errors, "family", japanese.family, korean.family, self.family_name_db)
            self._validate_component(errors, "given", japanese.given, korean.given, self.given_name_db)
        return errors

    @staticmethod
    def _validate_component(
        errors: List[str],
        name_type: str,
        japanese: str,
        korean: str,
        database: dict,
    ) -> None:
        info = database.get(japanese)
        if info is None:
            errors.append(f"{name_type} name is missing: {japanese}")
            return
        if not NameDB._translation_matches(info.get("kor"), korean):
            errors.append(f"{name_type} translation mismatch: {japanese} -> {korean}")

    def print_duplicate(self) -> None:
        for name, info in self.family_name_db.items():
            if isinstance(info["kor"], list):
                print(f"성: {name}", info["kor"])
        for name, info in self.given_name_db.items():
            if isinstance(info["kor"], list):
                print(f"이름: {name}", info["kor"])

    def add_full_name(self, full_name: str, kor: str, game: str) -> None:
        japanese = NamePair.parse(full_name)
        korean = NamePair.parse(kor)

        info = self.full_name_db.get(full_name)
        if info is not None:
            if kor != info["kor"]:
                raise ValueError(f"{full_name} {info['kor']} is different to {kor}.")
            self.add_game(full_name, game)
        else:
            self.full_name_db[full_name] = {"kor": kor, "game": [game]}

        self._add_component(japanese.family, korean.family, self.family_name_db, "Family")
        self._add_component(japanese.given, korean.given, self.given_name_db, "Given")

    @staticmethod
    def _translation_matches(existing: Translation, expected: str) -> bool:
        if isinstance(existing, list):
            return expected in existing
        return existing == expected

    @classmethod
    def _add_component(cls, japanese: str, korean: str, database: dict, label: str) -> None:
        info = database.get(japanese)
        if info is None:
            database[japanese] = {"kor": korean}
            return
        if not cls._translation_matches(info.get("kor"), korean):
            raise ValueError(f"{label} name: {japanese} {korean} is different to {info}.")
