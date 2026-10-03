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

`encode_translation`은 2바이트 글꼴 코드의 선행·후행 바이트와 MES 예약
제어 코드(`816F`, `8170`, `8190`, `8197`)를 검사한다. 게임에서 확인된
비표준 후행 바이트 코드는 `allowed_nonstandard_codes`에 정수 코드로
명시해야 한다. 이 허용 목록은 예약 제어 코드 검사를 우회하지 않는다.
MES 문법을 사용하지 않는 Marine 텍스트 DAT는 `forbidden_control_pairs`에
빈 집합을 전달한다. 문자 길이·선행·후행 바이트 검사는 그대로 적용된다.
DAT 치환도 `apply_replacements`를 사용하여 겹침과 잘못된 범위를 거부한다.

## 구조적 ASCII 추출과 검증

DOB1/DOB2의 JSON 생성은 확인된 `21 <printable ASCII> 00` 출력을 기본
구조 해석한다. 이전 JSON 추출 결과가 필요하면 decoder CLI에
`--no-structured-ascii`를 지정한다. 저수준 `decode_mes` 함수의 기본값은
기존 인코더·분석 도구 호환성을 위해 그대로 유지한다.

기존 번역을 옮길 때는 `python -m gspecific.adv_common.migrate_ascii`
도구를 사용한다. 변경된 번역 범위가 있으면 보고서만 생성하며 원문과
번역을 자동 재배치하지 않는다. DOB2 초기화의 `--force`도 동일 검증을
거치고, 모든 파일의 사전 검증이 끝나기 전에 기존 JSON을 쓰지 않는다.

MES 인코더의 `--patch-manifest`와 배치 인코더의 `--manifest-dir`는 실제
치환 범위·원본/출력 바이트·해시를 기록한다. DOB1의 매크로 치환은 `macro`,
크레디트 재구성은 `adapter`, 일반 번역은 `text`로 구분한다.
`verify_patch_manifest`는 선언된 치환과 나머지 원본 바이트를 모두 검사한다.
선언한 치환 자체의 게임 실행 의미를 증명하는 검사는 아니다.

사용법과 검증 결과는 [2순위 개선 기록](doc/ASCII_MIGRATION_VALIDATION.md)을 참고한다.

검증은 Conda base 환경에서 `compileall`과 실제 workspace의 원본 바이트
왕복 비교로 수행한다. 일회성 회귀 테스트 파일은 저장소에 보관하지 않는다.
