# europe Python 스크립트

- `gen_font_from_db.py`: 유럽 전선용 고정 단어와 긴 인명·지명을 기존 BMP 폰트 캔버스에 배치하고, 새 폰트 BMP와 `code.json`을 생성한다.
- `name_europe.py`: `europe_name.json`의 한국어 인명을 1바이트 글꼴 파일 목록과 비교해 누락된 글자를 출력한다. 현재 글꼴 경로가 코드에 고정되어 있다.
- `region_europe.py`: `europe_region.json`의 한국어 지명을 폰트 테이블로 인코딩했을 때 10바이트를 넘는 항목을 찾아 출력한다. 주석 처리된 부분은 DB 항목 추가용 보조 코드이다.
- `set_name.py`: 작업 공간의 일본어/한국어 스크립트 JSON 쌍에서 `europe_name.json`과 정확히 일치하는 인명을 찾아 한국어로 치환하고, 필요한 경우 주소 범위와 널 패딩을 조정한다.
- `set_region.py`: `europe_region.json`과 일치하는 지명을 한국어 스크립트에 반영한다. 폰트 테이블로 길이를 계산하며 10바이트를 넘는 번역은 건너뛴다.

이 스크립트들은 `C:/work_han/...` 작업 공간과 폰트 경로를 내부에 고정해 사용하므로 실행 전에 경로와 작업 공간 번호를 확인해야 한다.
