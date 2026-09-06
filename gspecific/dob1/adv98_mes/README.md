# Dead of the Brain ADV98 MES

누락 복구 도구: `recover_missing_text.py`는 현재 디코더로 원본 MES를 다시 검사하여 이전 info에서 빠진 대화와 오버레이를 복구합니다.

Dead of the Brain PC-98판의 ADV98 MES 스크립트를 추출하고 번역본으로
재구성하는 코드입니다. 다른 ADV98 게임과의 호환성은 보장하지 않습니다.

## 현재 사용 파일

- `decode_mes.py`: MES 해석 및 단일/일괄 일본어 JSON 추출
- `encode_mes_batch.py`: `*_info.json`과 `*_lang.json`에서 전체 번역 MES 인코딩
- `encode_mes.py`: 기존 `*_kor.json` 형식의 단일 MES 인코딩
- `translation_codec.py`: 원문·한글 문자열과 폰트 코드 인코딩 공통 함수
- `make_dialogue_dictionary.py`: 번역 대조 사전과 충돌 목록 생성
- `apply_dialogue_dictionary.py`: 충돌 없는 사전 번역을 `*_lang.json`에 적용
- `find_boundary_punctuation.py`: 화면 31·61셀의 `.`, `!`, `?` 검사
- `find_untracked_text.py`: lang에 등록되지 않은 화면 출력 후보를 검토용 JSON으로 추출
- `add_untracked_overlays.py`: 고신뢰 미등록 후보를 lang의 overlay 번역 대상으로 추가
- `link_overlay_texts.py`: 원본 MES를 분석하여 overlay의 연결 정보를 별도 출력 폴더에 준비한다.
- `control_codes.json`: 제어 코드 정의
- `macro_catalog.json`: ADV98 내장 매크로 정의
- `file_macro_overrides.json`: 파일별 매크로 예외
- `character_profiles.json`: 화자별 번역 말투 정보

과거 특정 번역 회차에만 사용한 보정·마이그레이션 스크립트는 제거했습니다.
현재 정식 빌드는 위 파일만 사용합니다.

## 전체 MES 빌드

저장소 루트에서 실행합니다.

```powershell
python -m gspecific.dob1.adv98_mes.encode_mes_batch `
  C:\work_han\workspace2
```

`script-pc98/MES/*_lang.json`을 검사하고 결과를 `kor-pc98/MES`에
생성합니다. 기본적으로 `kor-pc98-dosbox-x/MES`에도 복사하며,
복사하지 않으려면 `--no-dosbox-x`를 지정합니다.

## 원본 재추출

```powershell
python -m gspecific.dob1.adv98_mes.decode_mes `
  C:\work_han\workspace2\jpn-pc98 `
  C:\work_han\workspace2\script_init-pc98
```

## 번역 대조 사전

```powershell
python -m gspecific.dob1.adv98_mes.make_dialogue_dictionary `
  --workspace-dir C:\work_han\workspace2
```

기본 실행은 사전 내용을 실제 `*_lang.json`에 반영합니다.
`dictionary.json`의 단일 후보와, 수동으로 후보를 하나만 남긴
`annoying.json` 항목을 함께 사용합니다. `count` 값이 남아 있어도
실제 `translated` 배열에 후보가 하나면 확정 항목으로 처리합니다.

```powershell
python -m gspecific.dob1.adv98_mes.apply_dialogue_dictionary
```

파일을 수정하지 않고 변경 예정 건수만 확인하려면 `--dry-run`을 추가합니다.

```powershell
python -m gspecific.dob1.adv98_mes.apply_dialogue_dictionary --dry-run
```

번역이 비어 있는 항목만 채우려면 `--only-empty`를 함께 지정합니다.

`workspace2`에서 직접 실행할 수도 있습니다.

```powershell
cd C:\work_han\workspace2
python C:\work_han\translation\gspecific\dob1\adv98_mes\apply_dialogue_dictionary.py
```

## 줄바꿈 경계 문장부호 검사

```powershell
python -m gspecific.dob1.adv98_mes.find_boundary_punctuation
```

일반 문장부호와 `{.}`, `{!}`, `{?}` 제어 매크로뿐 아니라 번역의
`{...}` 안에 남은 일본어 문자·문장부호, `.`·`,` 뒤의 일반 공백도
검사합니다.

## 별도 역분석 도구

다음 파일은 MES 번역 빌드가 아니라 ADV98 실행 파일 분석용이므로
`gspecific/dob1/reverse_tools`에 분리해 둡니다.

- `adv98_dec.py`: TC0 래퍼 복호화
- `unpack_adv98_runtime.py`: Unicorn으로 self-extractor 실행 후 64 KiB dump
- `disasm_mz16.py`: MZ 또는 raw 16비트 코드 선형 디스어셈블

## Overlay 연결 정보

`python -m gspecific.dob1.adv98_mes.link_overlay_texts C:\work_han\workspace2 --output-dir .tmp/dob1_overlay_connections`

각 overlay의 `connections` 배열에는 같은 파일의 연결 대상 `id`와 원본 `offset`을 기록한다.
여러 구간이 이어지면 자신을 제외한 모든 연결 항목을 포함한다. ID가 없는 기존 overlay는
참조에서 `overlay:<offset>`으로 식별하며, 기존 항목의 필드는 유지한다.

원본 바이너리 전체를 디코딩하여 텍스트 사이에 구두점·공백 매크로 또는 `03` 메시지 UI
매크로만 있는 흐름을 연결한다. 새 화자, 다른 명령, 제어 코드, 분기 경계를 만나면 끊는다.
이미 dialogue segment에 포함된 overlay도 해당 dialogue와 연결한다.
이는 구조상 텍스트 흐름이며 동일 문장·화자나 게임 실행 시 경로를 확정하는 정보는 아니다.
빈 배열은 이 규칙으로 확인한 연결이 없다는 뜻이다. Marine Philt의 `BA 27 BA 23`
규칙은 DOB1에서 화자 매크로를 뜻하므로 사용하지 않는다.
