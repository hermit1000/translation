# ADV 공통 코드

DOB1, DOB2, Marine Philt의 MES 번역에서 재사용하는 기능이다.
공통 계열 명칭은 Juice의 엔진 구분에 맞춰 `ADV`로 사용한다.
Juice의 코드를 복사하거나 완전한 문법 호환성을 전제하지 않는다.

| 모듈 | 역할 |
| --- | --- |
| `tokens.py` | 토큰 생성, 문자 바이트 판정, 원본 바이트와 연속 범위 검증 |
| `ascii.py` | DOB2/Marine의 기존 ASCII 후보 판정, 토큰 병합, 외자 보존 |
| `text.py` | 원문 압축 문자 인코딩, 한글 폰트표 로딩 및 인코딩 |
| `patches.py` | 원본 오프셋 기준 교체 구간 검증과 결과 생성 |
| `audit_games.py` | DOB1/Marine 원본·번역을 읽어 명령 경계·ASCII·화자 보정 비교 보고서 생성 |

명령 해석, 화자/매크로, Marine selector, DOB1 크레디트와 선택지 등은
게임별 모듈에 유지한다. ASCII 판정은 기존 휴리스틱이며 명령 문법을
완전히 검증하지 않는다. 토큰 검증 역시 의미 해석의 정확성을 보장하지 않는다.

기존 `adv98_mes` 경로, CLI와 JSON format 식별자는 호환성을 위해 유지한다.
DOB1의 기존 helper import도 재노출하여 지원한다. 신규 공통 기능은
게임 모듈 대신 `gspecific.adv_common`에서 가져온다.

DOB2/Marine 인코더는 기존 화자 보정 로직을 공유하되 줄 경계 설정을
인자로 전달한다. 기존 width 규약의 31/28은 각각 실제 30/27셀을 뜻한다.
다른 게임 모듈의 전역 설정을 변경하지 않는다.
Marine은 DOB2 전용 화자 문자열 보정과 괄호 범위 확장을 사용하지 않는다.
조사 결과와 재현 명령은 [DOB1/Marine 분석](doc/DOB1_MARINE_ANALYSIS.md)을 따른다.

검증은 Conda base 환경에서 `compileall`과 실제 workspace의 원본 바이트
왕복 비교로 수행한다. 일회성 회귀 테스트 파일은 저장소에 보관하지 않는다.
