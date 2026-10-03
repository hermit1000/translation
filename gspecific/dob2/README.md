# Dead of the Brain 2 (PC-98)

## MES

`adv98_mes/`는 DOB2 전용 ADV98 MES 디코딩, 번역 JSON 초기화 및 단일
MES 인코딩 코드를 제공합니다.

번역하지 않고 원문을 의도적으로 유지할 항목은 DOB2 전용 예약어를
사용합니다.

```json
"translation": "@keep"
```

빈 문자열은 `incomplete`로 남지만, `@keep`은 원본 바이트를 유지하면서
`passed`로 처리됩니다. 이 예약어는 DOB1에는 적용되지 않습니다.

## GPC 이미지 인코딩·디코딩

공용 코덱은 `module.pc98_image.formats.adv98_gpc`이며, 바이너리·PNG 저장은
`module.pc98_image.adv98_artifacts.write_artifacts`를 사용합니다.
`gspecific.dob2.gpc`에는 대상 파일과 MES 출력 모드 선택만 남습니다.
DOB1·Marine Philt·Dracula와 동일한 실제 stride XOR 루틴을 사용합니다.


```powershell
python -m gspecific.dob2.gpc --workspace "<DOB2 작업폴더>"
```

`jpn-pc98/GPC/*.GPC`를 디코딩하여 다음 구조로 생성합니다.

```text
image-pc98/GPC/DB001.GPC/
  DB001.jpn.GPC
  DB001.pln.jpn.bin
  DB001.idx.jpn.bin
  DB001.jpn.png
  DB001.meta.json
```

전체 PNG를 한 번에 확인할 수 있도록 다음 폴더에도 PNG만 복사합니다.

```text
image-pc98/GPC/_png/*.jpn.png
```

MES의 `C9`/`CF` 사용을 조사해 각 파일의 출력 모드를 선택하며, 사용 기록이
없는 파일은 ADV98 GPC의 기본 모드 1로 디코딩합니다. 특정 모드를 강제하려면
`--mode 0` 또는 `--mode 1`을 사용합니다.

인코딩은 `module.pc98_image.formats.adv98_gpc.encode_gpc`에 원본 GPC와
수정한 픽셀 인덱스를 전달합니다. 원본 헤더·팔레트·interlace·stride를
보존하며, 다시 `decode_gpc`하여 입력 인덱스와 비교합니다.
API 및 검증 근거는 [공용 이미지 모듈](../../module/pc98_image/README.md)을
참조합니다. 위 명령의 작업폴더는 실제 DOB2 자료가 있는 경로로 지정합니다.
