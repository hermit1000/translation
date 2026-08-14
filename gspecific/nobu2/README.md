# nobu2 Python 스크립트

- `decode_graphics.py`: `jpn-pc98`의 알려진 그래픽 21개 파일을 `image-pc98/<원본 파일>/` 아래의 `*.jpn.png`, `log.json`, `report.html`로 추출한다. 지도 PAK 9개는 예외적으로 `image-pc98/MAP/`에 함께 저장하고 통합 로그·HTML을 만든다. EXE 내장 스프라이트, KAO 초상, `0x96` PAK, ANM 이미지 bank, 문장·지형과 HEXMAP 진단 이미지를 지원한다.
- `decode_graphics_384k.py`: 384K판의 `jpn-pc98-384k`를 읽어 `image-pc98-384k/`에 추출한다. `KAO.DAT`, `MAP.DAT`, `HYOSI.DAT`, `ODAANM.DAT`, `SEISHIGA.DAT`로 합쳐진 그래픽과 384K판 `ODAMAIN.EXE` 내장 프레임을 전용 오프셋으로 처리한다.
- `make_korean_graphics.py`: `binary_inputs-pc98/<원본 파일명>/`에 있는 `TITLE.bg.png`와 `END2.bg.png`를 직접 참조하고, 같은 폴더에 각각 `TITLE.kor.png`, `END2.kor.png`를 만든다. 폴더별 수동 합성 루틴을 사용하며 새 대상은 코드의 `MANUAL_JOBS`에 명시적으로 추가한다.
- `make_map_graphics.py`: 지도용 순번·한글 표시 문자열과 좌표를 Python 상수로 보관한다. 주소와 `{}` 등의 스크립트 코드 표기는 제외한다. `MAP17`과 7개 지역 지도(`TOUHOKU`, `HOKURIKU`, `KANTOU`, `TYUBU`, `KINKI`, `SHIKOKU`, `KYUSYU`)는 각각의 `*.jpn.png`에서 원본 번호 픽셀을 복사하고, `*.PAK.BG.png` 위에 `Maplestory Light.ttf` 한글 지명을 합성해 `*.PAK.KOR.png`로 만든다. MAP17 외 지도는 DATA50 중 실제 지도에 포함된 번호만 등록한다. 일반적으로 같은 번호의 설정을 공유하되, TYUBU처럼 원본 배치가 다른 지도는 전용 값을 사용한다.
- `encode_graphics.py`: `binary_inputs-pc98`에서 수동 등록된 `ODAMAIN.EXE`, `TITLE.PAK`, `END2.PAK`와 지도 PAK 8개를 인코딩한다. 내장 프레임은 `*.pln.kor.bin`으로 만들고, 최종 PAK는 작업 폴더에 원본 파일명 그대로 저장한다. 지도는 공용 `binary_inputs-pc98/MAP` 폴더의 `*.PAK.KOR.png`를 읽고 같은 폴더에 `*.PAK`와 통합 `encode_log.json`을 만든다. `MAP17`, `KINKI`, `TYUBU`는 384K판의 고정 슬롯에도 들어가도록 패딩하지 않으며, 나머지는 기본적으로 원본 크기까지 `0x1A`로 패딩한다. 인코딩 후 384K 작업공간이 있으면 `ODAMAIN.EXE`, `HYOSI.DAT`, `MAP.DAT`의 `binary_input`도 자동 갱신한다. TITLE/END2는 기존 크기 제한을 유지한다.
- `pc98_image_codec.py`: 공용 PC-98 interleaved planar 변환과 Nobu2 전용 `0x96` vertical-copy PAK 압축·해제를 연결하는 코덱 모듈이다.
- `gen_font_from_db_nobu2.py`: `NameDB`의 NB2 인명과 고정 단어·지명을 모아 한국어 폰트 BMP를 구성하고, 문자열과 코드의 대응표인 `custom_word.json`을 생성한다.
- `set_code_from_db_nobu2.py`: `DATA17.DAT`, `DATA50.DAT`, `ODAMAIN.EXE`의 스크립트 JSON에서 성명 배열을 읽어 `NameDB`의 한국어 이름으로 변환하고 길이와 주소를 맞춘다. 기본값 `save = False`에서는 변경 예정 내용만 출력하므로 실제 저장 시 값을 명시적으로 바꿔야 한다.

이미지 스크립트의 `--workspace` 기본값은 `c:/work_han/workspace0`이다. decoder의 기본 실행은 PNG·`log.json`·`report.html`을 만들며, `--all-artifacts`를 지정하면 planar 바이너리와 contact sheet도 만든다. 한국어 합성과 encoder 결과는 삽입 입력이 모인 `binary_inputs-pc98`에 직접 생성된다. 자동 폴더 검색을 하지 않으므로 지원 대상을 추가할 때는 해당 수동 job 목록과 전용 루틴을 함께 추가해야 한다. 기존 글꼴·문자열 스크립트는 `C:/work_han/...` 경로와 작업 공간 번호를 내부 설정으로 사용한다.

`encode_graphics.py`를 실행하면 기본적으로 배경 합성과 인코딩을 연속 수행하므로 `binary_inputs-pc98`의 PNG와 최종 바이너리를 한 번에 갱신한다. 기존 `*.kor.png`를 다시 합성하지 않고 인코딩만 하려면 `--no-compose`를 지정한다.
