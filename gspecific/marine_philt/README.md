# Marine Philt 이미지 도구

GPC 인코딩·디코딩은 `module.pc98_image.formats.adv98_gpc`를 사용한다.
`gspecific.marine_philt.gpc`는 파일 목록과 MES 출력 모드를 선택하고
`module.pc98_image.adv98_artifacts.write_artifacts`로 생성물을 저장한다.

```powershell
python -m gspecific.marine_philt.gpc --workspace "<Marine Philt 작업폴더>"
```

원본은 `jpn-pc98/GRAPH/*.GPC`, 생성물은
`image-pc98/GPC/<원본파일명>/`의 바이너리·PNG·메타데이터다.
`--file`과 `--mode 0`/`--mode 1`을 사용할 수 있다.

인코딩은 공용 `encode_gpc`에 원본 GPC와 편집한 픽셀 인덱스를 전달하고,
같은 모드로 `decode_gpc`하여 왕복 검증한다. 원본 헤더·팔레트·stride·interlace를
보존한다. `MARINE.OV1.dec`의 stride XOR 루틴은 DOB1/DOB2/Dracula와
명령 바이트까지 동일하며 Necronomicon의 XOR 핵심도 같다.

[공용 API](../../module/pc98_image/README.md)와
[실제 루틴 검증](../dob1/GPC_RUNTIME_ANALYSIS.md)을 참조한다.
