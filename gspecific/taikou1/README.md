# taikou1 Python 스크립트

- `pc98_image_codec.py`: PC-98 인덱스/플래너 이미지 변환, 게임 전용 RLE/LZ 압축·해제, 매니페스트 읽기와 HTML 미리보기 생성을 제공하는 공용 모듈이다.
- `decode_raw_planar.py`: `jpn-pc98`의 고정 크기 planar block을 `image-pc98/<원본 파일>/` 아래의 `pln.jpn`, `idx.jpn`, `jpn.png`와 메타데이터로 추출한다.
- `encode_raw_planar.py`: 같은 폴더의 오프셋명 `*.kor.png`를 원본 layout의 `*.pln.kor.bin`으로 재인코딩한다.
- `decode_rle_lz.py`: `jpn-pc98`의 이미지 아카이브를 순회하며 RLE/LZ 프레임을 `cmp.jpn`, `idx.jpn`, `jpn.png`와 메타데이터로 추출한다.
- `encode_rle_lz.py`: 같은 폴더의 `*.kor.png`를 삽입 가능한 `*.cmp.kor.bin`으로 만든다. 기본적으로 원본 압축 크기까지 널 패딩하며 `--no-padding`으로 끌 수 있다.
- `gen_font_from_db_taiko1.py`: Taikou 1 인명과 고정 지명·문구에 필요한 글꼴을 기존 BMP 캔버스에 배치해 새 폰트 BMP와 `custom_word.json`을 생성한다.
- `set_code_from_db_taiko1.py`: `TBS.DAT`와 `MAIN.EXE`의 성/이름 항목을 `NameDB`의 한국어 이름 토큰으로 바꾸고 일본어/한국어 스크립트 JSON의 길이와 주소를 함께 조정한다.

네 이미지 변환 스크립트의 `--workspace` 기본값은 `c:/work_han/workspace`이며, 필요하면 다른 경로를 지정할 수 있다. 작업 공간에서는 `jpn-pc98`과 `image-pc98`을 사용한다. 대상 파일 목록과 프레임 규격은 decoder 내부 상수로 정의되어 있다.

기본 실행에서는 decoder가 편집용 `*.jpn.png`, `log.json`, `report.html`을 만들고 encoder가 삽입용 `*.kor.bin`과 `log.json`을 만든다. 중간 planar/compressed/index 바이너리, 프레임별 메타데이터와 시트가 필요하면 `--all-artifacts`를 지정한다.
