# nobu4 Python 스크립트

- `gen_all_name_nb4.py`: NB4 인명·지역·산천성·다기 DB의 한국어 문자열을 글자별 BMP에서 조합해 확인용 이름 이미지를 `font_update_db/test`에 생성한다.
- `gen_font_from_db_nobu4.py`: NB4 인명과 지명, 산천성, 다기 및 고정 문구에 필요한 1바이트/다글자 글꼴을 폰트 캔버스에 배치하고 `nobu4-*.bmp`와 `custom_word.json`을 만든다.
- `set_code_from_db_nobu4.py`: `MAIN.EXE`와 `SNDATA*.CIM`의 일본어/한국어 스크립트 JSON에서 성과 이름을 쌍으로 읽고, `NameDB`의 한국어 이름 토큰으로 교체하면서 길이와 주소 범위를 정렬한다.

입력 DB, 폰트 및 작업 공간 경로가 `C:/work_han/...`로 고정되어 있으므로 실행 전 내부 설정을 확인해야 한다.
