import json
import re
from collections import OrderedDict
from pathlib import Path


WORKSPACE = Path("c:/work_han/workspace5")
EXT_SCRIPT_PATH = WORKSPACE / "script-pc98/MAIN.EXE_jpn_ext.json"
OUTPUT_PATH = WORKSPACE / "메뉴.txt"


TRANSLATIONS = {
    "◎": "◎",
    "－": "-",
    "決定": "결정",
    "間終": "턴 종료",
    "農業開発": "농업개발",
    "商業奨励": "상업장려",
    "領内巡検": "영내순찰",
    "作事改修": "공사수리",
    "築城普請": "축성공사",
    "評定": "평정",
    "開戦": "개전",
    "雇足軽": "아시가루 고용",
    "訓練": "훈련",
    "移動": "이동",
    "輸送": "수송",
    "会盟": "회맹",
    "威圧": "위압",
    "恭順": "공순",
    "婚姻": "혼인",
    "手切れ": "결별",
    "朝廷工作": "조정공작",
    "他城偵察": "타성정찰",
    "内応勧誘": "내응권유",
    "煽動": "선동",
    "流言飛語": "유언비어",
    "暗殺": "암살",
    "取立": "징수",
    "隠居": "은거",
    "縁組": "혼맥",
    "任命": "임명",
    "国主指示": "국주지시",
    "論功行賞": "논공행상",
    "購入": "구입",
    "売却": "매각",
    "対外関係": "대외관계",
    "勢力分布": "세력분포",
    "所領一覽": "영지일람",
    "家臣一覽": "가신일람",
    "家": "가문",
    "録中": "기록 중",
    "録止": "기록 중지",
    "取消": "취소",
    "最大": "최대",
    "国主一任": "국주일임",
    "増減": "증감",
    "切放": "방출",
    "出陣": "출진",
    "和議": "화의",
    "退伏": "항복",
    "退伏勧告": "항복권고",
    "和議要請": "화의요청",
    "籠城": "농성",
    "交戦": "교전",
    "工作": "공작",
    "軍議": "군의",
    "挑伝": "도발",
    "靜觀": "관망",
    "守備": "수비",
    "砲攻": "포격",
    "内応": "내응",
    "兵糧補恩": "병량보급",
    "鼓舞": "고무",
}


NEEDS_REVIEW = {
    "月効",
    "新賞",
    "与奨報",
    "金任",
    "叙状",
    "一感学領",
    "拝懲",
    "転没",
    "今却",
    "平攻",
    "持任",
    "腹通移動",
    "常方封向",
    "換行移動",
    "腹通平攻",
    "撃攻",
    "物発",
    "め入",
    "突平火",
    "力平火",
    "▽平正",
    "法久戦",
}


def resolve_path(path: Path) -> Path:
    if path.exists():
        return path
    path_text = str(path)
    if len(path_text) >= 3 and path_text[1:3] == ":/":
        wsl_path = Path("/mnt") / path_text[0].lower() / path_text[3:]
        if wsl_path.exists() or wsl_path.parent.exists():
            return wsl_path
    return path


def clean_ext_text(text: str) -> str:
    text = re.sub(r"\{([^}:]+)(?::[^}]+)?\}", r"\1", text)
    text = re.sub(r"\|.", "", text)
    return text.replace("_", "")


def split_terms(text: str) -> list[str]:
    terms = []
    index = 0
    known_terms = sorted(TRANSLATIONS, key=len, reverse=True)
    review_terms = sorted(NEEDS_REVIEW, key=len, reverse=True)
    candidates = known_terms + [term for term in review_terms if term not in TRANSLATIONS]

    while index < len(text):
        for term in candidates:
            if text.startswith(term, index):
                terms.append(term)
                index += len(term)
                break
        else:
            terms.append(text[index:])
            break
    return [term for term in terms if term]


def collect_terms(ext_script: dict[str, str]) -> OrderedDict[str, list[str]]:
    terms: OrderedDict[str, list[str]] = OrderedDict()
    for address, text in ext_script.items():
        cleaned = clean_ext_text(text)
        for term in split_terms(cleaned):
            terms.setdefault(term, []).append(address)
    return terms


def build_lines(terms: OrderedDict[str, list[str]]) -> list[str]:
    lines = [
        "일본어\t한국어\t주소\t비고",
    ]
    for japanese, addresses in terms.items():
        korean = TRANSLATIONS.get(japanese, "")
        note = "확인 필요" if japanese in NEEDS_REVIEW or not korean else ""
        lines.append(f"{japanese}\t{korean}\t{', '.join(addresses)}\t{note}")
    return lines


def main() -> None:
    ext_script_path = resolve_path(EXT_SCRIPT_PATH)
    with ext_script_path.open("r", encoding="utf-8") as file:
        ext_script = json.load(file)

    output_path = resolve_path(OUTPUT_PATH)
    output_path.write_text("\n".join(build_lines(collect_terms(ext_script))) + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
