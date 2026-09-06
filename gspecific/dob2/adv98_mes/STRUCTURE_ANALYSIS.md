# DOB2의 ASCII 출력과 화자 주변 구조 분석

2026-09-06, workspace1의 원본 MES 117개를 읽기 전용으로 비교했다.
Juice ADV의 `CHRS!` 문자열 문법을 참고했으며 Racket 코드를 복사하지 않았다.
게임 실행 파일의 명령 처리 루틴이나 실제 화면으로 의미를 확정한 분석은 아니다.

## ASCII 출력

기존 lexer가 도달한 토큰 경계에서 `21 <20..7E 바이트> 00`을 인식한다.
명령 인자나 Shift-JIS 바이트 내부를 검색하여 출력 시작점으로 삼지 않는다.
시작/종료 제어 바이트와 표시 문자열은 별도 토큰으로 보존한다.
확인하지 않은 혼합 Shift-JIS 문자열, FF 종료, 미종결 문자열에는 적용하지 않는다.
그 밖의 영역은 기존 ASCII 휴리스틱으로 처리한다.

- 인식한 출력 구간: 2,311개
- 기존 대비 변경된 텍스트 레코드: 6개
- INIT.MES 0056A: 마지막 쉼표가 숫자 인자로 처리되어 빠지던 문제를 교정
- OPENNING.MES 003AE: 압축 문자로 오해석하던 `32`를 ASCII 숫자 `2`로 해석
- MUSIC.MES 00111, OPENNING.MES 00151/0092C/00969: 공백 한 글자 출력 보존

INIT.MES 0056A에는 기존 번역이 있다. 신규 원문에는 쉼표가 추가되어 원문 및
범위가 달라지므로 기존 info/lang을 덮어쓰지 말고 함께 검토해야 한다.
공백만 있는 레코드는 기존 번역 초기화 규칙의 `strip()` 검사로 제외된다.

## CONTROL_08 주변

기존 CONTROL_08 토큰 바로 뒤 또는 한 바이트 뒤에 전각 화자 괄호가 있는
패턴 713건을 찾았다. 이 중 51건은 기존 두 바이트 CONTROL_08 토큰이
여는 괄호 `81 6D`의 선행 바이트 `81`을 소비한다.

그러나 `08 A3 ...` 등 다른 구조도 존재한다. 따라서 08의 고정 인자 개수나
화자 ID 의미를 확정하지 않았다. 보고서는 control/label 오프셋, 괄호 사이
이름, 중간 바이트, 기존 괄호 분할 여부만 기록한다. 대사 범위나 인코더의
기존 호환 보정은 변경하지 않는다.

## 사용

저장소 루트, Conda base 환경에서 실행한다.

```powershell
python -m gspecific.dob2.adv98_mes.analyze_mes C:\work_han\workspace1\jpn-pc98\MES .tmp\dob2_structure_report.json
python -m gspecific.dob2.adv98_mes.decode_mes C:\work_han\workspace1\jpn-pc98\MES .tmp\dob2_structured --structured-ascii
```

기존 CLI와 함수는 기본적으로 이전 토큰 경계를 유지한다.
Python에서는 `decode_mes(data, structured_ascii=True)`로 새 처리를 사용한다.
분석 보고서는 각 레코드의 변경 전후 원문·범위·원본 바이트를 포함한다.

## 검증

- 새 구조 해석: DOB2 117개 모두 원본 바이트 및 토큰 범위 검증 통과
- 기본 동작: DOB1 82개, DOB2 117개, Marine Philt 134개 기존 토큰 결과 동일
- ASCII 문장부호/숫자/공백, 인자 내부 오탐 방지, 미종결 및 비ASCII 입력,
  두 가지 화자 괄호 배치와 비화자 CONTROL_08 패턴을 확인하는 일회성 검증을 수행
- 기존 info/lang 및 게임 바이너리는 변경하지 않음. 게임 실행 검증은 미수행
