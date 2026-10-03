# MES 공통 도구

공통 MES 라이브러리는 `mes/adv_common`에 있으며, 실행·검증 도구는 이 디렉터리에 둡니다.

- `audit_games.py`: 게임별 MES 구현 감사
- `migrate_ascii.py`: ASCII/문자열 마이그레이션 보조
- `translation_bundles.py`: 번역 bundle 생성 및 `*_translated.json` 병합
- `make_keep_bundles.py`: `@keep` 항목과 같은 `display_group`의 문맥 대사 생성

## `audit_games.py`

`audit_games.py`는 DOB1과 Marine Philt의 MES 번역 구조를 읽기 전용으로
점검하는 감사·비교 도구다. 원본 및 번역 파일은 수정하지 않고 JSON 보고서만
생성한다. 완전한 제어 흐름 분석기나 게임 실행 검증기는 아니다.

주요 점검 항목은 다음과 같다.

- DOB1의 raw `BA` 매크로 탐지 결과와 lexer의 `CALL_BUILTIN` 경계 비교
- DOB1/Marine의 ASCII 추출 전후 및 텍스트 레코드 변경 비교
- Marine selector/parameter 영역과 원본 바이트 기록
- Marine `*_info.json`, `*_lang.json`의 원본 해시·offset·`raw_hex` 일치 여부 검증
- Marine 번역문의 폰트 테이블 인코딩 성공·실패 및 화자 보정 전후 결과 비교
- 번역 범위 오류, 메타데이터 불일치, 인코딩 오류 보고

입력은 DOB1 workspace, Marine workspace, 출력 JSON 경로이며, 선택적으로
`--font-table`로 사용할 한글 폰트 테이블을 지정할 수 있다.

```powershell
python -m mes.tools.audit_games `
  C:\work_han\workspace2 `
  C:\work_han\workspace4 `
  .tmp\dob1_marine_audit.json
```

기존 import 경로 호환이 필요한 경우 `gspecific.adv_common.audit_games`도
사용할 수 있다.

작업폴더의 `script-pc98`에서 실행하는 예:

```powershell
python C:\work_han\translation\mes\tools\translation_bundles.py make
python C:\work_han\translation\mes\tools\translation_bundles.py make-keep
python C:\work_han\translation\mes\tools\translation_bundles.py apply
python C:\work_han\translation\mes\tools\translation_bundles.py apply --check-only
```

기본 경로는 명령을 실행한 현재 폴더의 `MES`와 현재 폴더입니다. 다른 위치는
`--mes-dir`, `--output-dir` 또는 `apply`의 bundle 폴더 인자로 지정할 수 있습니다.

게임별 디코더와 인코더는 각 게임의 `gspecific/<game>/adv98_mes`에 유지합니다.
