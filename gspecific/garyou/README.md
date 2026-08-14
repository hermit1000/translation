# garyou Python 스크립트

- `end_dat_to_png.py`: `c:/work_han/workspace/jpn-pc98`의 `END_S*.DAT`를 일괄 탐색해 RLE 해제하고, 이미지 번호에 맞는 `ENDPAL.GRG` 또는 `ENDPAL.BRG` 팔레트로 변환한다. 결과는 하위 파일 폴더 없이 `graphic-pc98/END_Sn.jpn.png`에 직접 저장하며 `log.json`과 `report.html`을 함께 만든다. `--all-artifacts`를 지정하면 native·planar·indexed·metadata 파일도 추가한다.
- `end_png_to_dat.py`: `c:/work_han/workspace/binary_inputs-pc98`의 `*.kor.png`를 일괄 탐색한다. 각 640×400 PNG를 원본별 팔레트 인덱스와 planar/RLE 형식으로 변환해 같은 폴더에 `*.kor.DAT`와 `encode_log.json`을 만든다. `--verify`를 사용하면 생성 DAT를 다시 디코딩해 픽셀 인덱스를 검증하고, `--all-artifacts`를 사용하면 idx·planar·metadata도 추가한다.

두 스크립트의 `--workspace` 기본값은 `c:/work_han/workspace`이다. decoder는 `graphic-pc98`에 원본 PNG를 펼치고, encoder는 최종 삽입 자료가 있는 `binary_inputs-pc98`에서 한국어 PNG를 읽고 DAT를 출력한다.
