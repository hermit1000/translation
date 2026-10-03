# Dead of the Brain 1 이미지 도구

GPC 인코딩·디코딩은 `module.pc98_image.formats.adv98_gpc`를 사용한다.
`gspecific.dob1.gpc`는 기존 CLI와 import 호환 경로이며, 자체 코덱을 갖지 않는다.
파일 저장과 정확한 PNG 팔레트 매핑은 `module.pc98_image.adv98_artifacts`를 사용한다.

```powershell
python -m gspecific.dob1.gpc --workspace "<DOB1 작업폴더>"
python -m gspecific.dob1.encode_korean_images --workspace "<DOB1 작업폴더>"
```

디코더는 `jpn-pc98/GRAPH/*.GPC`를 읽고
`image-pc98/GRAPH/<원본파일명>/`에 바이너리·PNG·메타데이터를 저장한다.
`--file` 및 `--mode 0`/`--mode 1`로 대상을 지정할 수 있다.

한국어 이미지 도구는 FRR/BLTY의 파일 경로와 기존 FRR 보정 옵션을 선택하는
실행 도구다. 표준 인코딩과 XOR 역변환은 공용 코덱을 사용한다.
FRR의 명시적 `runtime_compatibility` 비트 보정은 공용 인코더 밖에 유지한다.

새 인코더는 공용 `encode_gpc(source_bytes, indices, output_mode=...)`를 사용하고,
다시 `decode_gpc`하여 입력 인덱스와 비교한다. 원본 헤더·팔레트·interlace·stride를
보존하며, 게임에 맞는 패키징과 출력 위치는 호출자가 결정한다.

[공용 API](../../module/pc98_image/README.md)와
[실제 루틴 검증](GPC_RUNTIME_ANALYSIS.md)을 참조한다.
