# Dead of the Brain ADV98 MES

Dead of the Brain PC-98판의 ADV98 MES 스크립트를 추출하고 번역본으로
재구성하는 코드입니다. 다른 ADV98 게임과의 호환성은 보장하지 않습니다.

## 현재 사용 파일

- `decode_mes.py`: MES 해석 및 단일/일괄 일본어 JSON 추출
- `encode_mes_batch.py`: `*_info.json`과 `*_lang.json`에서 전체 번역 MES 인코딩
- `build_workspace.py`: workspace 전체 MES 일괄 빌드 진입점
- `encode_mes.py`: 기존 `*_kor.json` 형식의 단일 MES 인코딩
- `translation_codec.py`: 원문·한글 문자열과 폰트 코드 인코딩 공통 함수
- `make_dialogue_dictionary.py`: 번역 대조 사전과 충돌 목록 생성
- `control_codes.json`: 제어 코드 정의
- `macro_catalog.json`: ADV98 내장 매크로 정의
- `file_macro_overrides.json`: 파일별 매크로 예외
- `character_profiles.json`: 화자별 번역 말투 정보

과거 특정 번역 회차에만 사용한 보정·마이그레이션 스크립트는 제거했습니다.
현재 정식 빌드는 위 파일만 사용합니다.

## 전체 MES 빌드

저장소 루트에서 실행합니다.

```powershell
python -m gspecific.dob1.adv98_mes.build_workspace `
  C:\work_han\workspace2 --dosbox-x
```

`script-pc98/MES/*_lang.json`이 있으면 현재 lang 기반 빌드를 사용하며,
결과는 `kor-pc98/MES`에 생성됩니다. `--dosbox-x`를 지정하면
`kor-pc98-dosbox-x/MES`에도 복사합니다.

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

## 별도 역분석 도구

다음 파일은 MES 번역 빌드가 아니라 ADV98 실행 파일 분석용이므로
`gspecific/dob1/reverse_tools`에 분리해 둡니다.

- `adv98_dec.py`: TC0 래퍼 복호화
- `unpack_adv98_runtime.py`: Unicorn으로 self-extractor 실행 후 64 KiB dump
- `disasm_mz16.py`: MZ 또는 raw 16비트 코드 선형 디스어셈블
