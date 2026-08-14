# taikou2 Python 스크립트

- `gen_font_from_db_taiko2.py`: Taikou 2 인명과 고정 지명·조사에서 필요한 글자 조합을 폰트 캔버스에 배치해 `taikou2-*.bmp`와 `code.json`을 생성한다.
- `set_code_from_db_taiko2.py`: `SNDATA1.TR2`와 `SNDATA2.TR2`의 성/이름 항목을 `NameDB`의 한국어 이름 토큰으로 치환하고, 일본어/한국어 스크립트 JSON의 길이와 주소 범위를 정렬한다.
- `update_checksum.py`: TR2 파일의 시드로 XOR 키를 계산하고 데이터 영역의 체크섬을 검증하거나 갱신하는 `TR2ChecksumTool`을 제공한다. 현재 직접 실행 시에는 검사만 하며 실제 저장 호출은 주석 처리되어 있다.

대상 파일과 `C:/work_han/...` 작업 경로가 코드에 지정되어 있으므로 실행 전 내부 설정을 확인해야 한다.
