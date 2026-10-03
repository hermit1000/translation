# Necronomicon (PC-98)

Necronomicon의 `MES`는 기존 ADV98 계열과 같은 압축 문자·제어 코드 구조를
사용한다. 디코더는 DOB2의 저수준 해석기를 재사용하지만, Necronomicon 전용
`info/lang` 형식과 `「화자」` 대화 판정을 사용한다.

대화창은 한 줄 32자(일본어 전각 기준 64바이트)를 사용한다. 인코더는
32자 경계 직후의 단일 정렬 공백을 제거하고, 연속 공백은 다음 줄 들여쓰기로
보존한다. `A5`뿐 아니라 대화 위치를 갱신하는 `A7` 뒤의 텍스트도 같은
화면의 continuation으로 분석해 번역 화자 길이에 맞춰 들여쓴다.

## 원문 추출

```powershell
python -m gspecific.necronomicon.adv98_mes.decode_mes `
  C:\work_han\workspace1\jpn-pc98\MES `
  C:\work_han\workspace1\script-pc98\MES
```

기존 JSON을 덮어쓸 때만 `--force`를 사용한다. 원본의 `source_sha256`와
레코드별 `raw_hex`는 인코딩 전에 원본 MES가 바뀌지 않았는지 검증하는 데
사용된다.

## 번역 사전

```powershell
python -m gspecific.necronomicon.adv98_mes.make_dialogue_dictionary
python -m gspecific.necronomicon.adv98_mes.apply_dialogue_dictionary --dry-run
```

`dictionary.json`의 단일 번역 후보와 수동으로 정리한 `annoying.json`을
사용한다. 실제 반영은 `--dry-run`을 제거한다.

## MES 생성

```powershell
python -m gspecific.necronomicon.adv98_mes.encode_mes_batch `
  C:\work_han\workspace1 `
  --font-table C:\work_han\translation\gspecific\necronomicon\font_table-kor-jin-necro-compact.json
```

번역 결과는 `kor-pc98\MES`에 생성되고, 기본적으로
`kor-pc98-dosbox-x\MES`에도 복사된다. 줄 폭을 임의로 보정하지 않으며,
번역문에 입력한 공백과 개행용 공백을 그대로 인코딩한다.

배치 인코더는 기본적으로 `necro_compact_font_mapping_top20.json`과
`font_table-kor-jin-necro-compact.json`을 사용해
선택된 빈도 상위 문자를 ADV98의 1바이트 압축 문자 슬롯으로 저장한다.
실행 시에는 작업폴더의 `necro-ThinDungGeunMo.bmp`를
DOSBox-X의 Anex86 폰트로 사용해야 한다. 기존처럼 모든 번역 문자를
2바이트 폰트 코드로 저장하려면 `--no-compact-remap`을 지정한다.

## SYSTEM.MEC 선택창

`移動`, `持ち物`, `セーブ`, `デバッグ`, `ファイル０`~`ファイル６`,
`キャンセル` 같은 선택창 문구는 MES가 아니라 `MES/SYSTEM.MEC`에 들어
있다. 전용 디코더와 인코더를 사용한다.

문자열의 오프셋·길이·원문 바이트 정의는
`system_mec_texts.json`에 별도로 보관한다. 새로운 SYSTEM.MEC 선택창
문구를 발견하면 이 JSON에 항목을 추가한 뒤 디코더를 다시 실행한다.

```powershell
python -m gspecific.necronomicon.decode_system_mec `
  C:\work_han\workspace1\jpn-pc98\MES\SYSTEM.MEC `
  C:\work_han\workspace1\script-pc98\MES\SYSTEM.MEC_info.json `
  C:\work_han\workspace1\script-pc98\MES\SYSTEM.MEC_lang.json

python -m gspecific.necronomicon.encode_system_mec `
  C:\work_han\workspace1\jpn-pc98\MES\SYSTEM.MEC `
  C:\work_han\workspace1\script-pc98\MES\SYSTEM.MEC_info.json `
  C:\work_han\workspace1\script-pc98\MES\SYSTEM.MEC_lang.json `
  C:\work_han\workspace1\kor-pc98-dosbox-x\MES\SYSTEM.MEC
```

`소지품`은 `소`와 `품`을 2바이트 코드로, `지`를 compact 1바이트 코드
`0x32`로 저장한다. 따라서 원문의 `持ち物`과 같은 5바이트를 유지한다.
`저장`처럼 원문 슬롯보다 짧은 번역은 전각 공백으로 슬롯을 채워
`SYSTEM.MEC` 내부의 후속 오프셋을 밀어내지 않는다.

`MAP.MEC`도 같은 도구에 별도 텍스트 정의를 지정해 처리한다.

```powershell
python -m gspecific.necronomicon.decode_system_mec `
  C:\work_han\workspace1\jpn-pc98\MES\MAP.MEC `
  C:\work_han\workspace1\script-pc98\MES\MAP.MEC_info.json `
  C:\work_han\workspace1\script-pc98\MES\MAP.MEC_lang.json `
  --text-spec C:\work_han\translation\gspecific\necronomicon\map_mec_texts.json

python -m gspecific.necronomicon.encode_system_mec `
  C:\work_han\workspace1\jpn-pc98\MES\MAP.MEC `
  C:\work_han\workspace1\script-pc98\MES\MAP.MEC_info.json `
  C:\work_han\workspace1\script-pc98\MES\MAP.MEC_lang.json `
  C:\work_han\workspace1\kor-pc98\MES\MAP.MEC
```

## GPC 이미지 인코딩·디코딩

실제 코덱은 `module.pc98_image.formats.adv98_gpc`를 사용한다.
전용 `decode_gpc.py`는 Necronomicon 헤더 변형, DAC 팔레트, 파일 목록,
TCM 추출 및 기존 저장 위치를 선택하는 실행 도구다.

```powershell
python -m gspecific.necronomicon.decode_gpc --workspace C:\work_han\workspace1
python -m gspecific.necronomicon.decode_gpc --workspace C:\work_han\workspace1 --tcm-only
```

- standalone 바이너리·메타데이터: `image-pc98/GPC/`
- PNG 및 전체 복원 raw PNG: `image-pc98/PNG/`
- TCM에서 추출한 GPC·메타데이터: `image-pc98/TCM/`

TITLE은 AL을 stride 체인 사이에 유지하는 실제 XOR 루틴으로 전체
640×400을 복원한다. 높이 자르기 없이 기준 캡처와 RGB가 완전히 일치한다.
기존 TMAST 표시용 높이 보정은 게임 실행 도구에만 남아 있고, raw PNG와
공용 코덱에는 적용하지 않는다.

새 GPC 인코딩은 공용 `encode_gpc(..., variant="necronomicon")`를 사용한다.
원본의 zero-size/inclusive-size 헤더 관례를 유지하며 인덱스로 왕복 검증한다.
mode 1 리소스는 기존 실행 도구와 같은 `cumulative_xor=False`를 지정한다.
팔레트 RGB 표현과 XOR 검증 근거는
[`module/pc98_image/README.md`](../../module/pc98_image/README.md)와
[`GPC_RUNTIME_ANALYSIS.md`](../dob1/GPC_RUNTIME_ANALYSIS.md)를 참조한다.
