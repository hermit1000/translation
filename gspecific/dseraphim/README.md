# dseraphim Python 스크립트

- `extract_ass.py`: `OPEN.ASS`와 `END.ASS`의 압축 데이터를 해제하고, 지정된 텍스트 영역을 일본어 폰트 테이블로 디코딩해 JSON으로 저장한다. 입력·출력 폴더와 폰트 테이블은 명령행 옵션으로 지정할 수 있다.
- `build_kor_ass.py`: 번역된 한국어 JSON을 폰트 코드로 변환해 원본 `OPEN.ASS`/`END.ASS` 템플릿에 반영하고 `OPEN_kor.ASS`와 `END_kor.ASS`를 만든다. 저장 전에 RLE/LZ 재압축 결과를 다시 해제하여 원본 패치 데이터와 일치하는지 검증한다.

두 스크립트는 기본적으로 현재 디렉터리의 입력 파일을 사용한다. `build_kor_ass.py`는 같은 폴더의 `extract_ass.py`를 모듈로도 사용한다.
