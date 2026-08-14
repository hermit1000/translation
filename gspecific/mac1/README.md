# mac1 Python 스크립트

- `decode.py`: `jpn-pc98`의 커스텀 `.IMG` 헤더와 Delta+RLE 데이터를 해제하고 파일별 `image-pc98` 폴더에 원본, planar, index와 회색조 PNG를 저장한다.
- `codec.py`: `.IMG`용 열 우선 순회 순서를 만들고 Delta+RLE 압축을 수행한다. 직접 실행하면 `image-pc98`의 `*.pln.jpn.bin`을 압축해 원본 IMG 페이로드와 비교한다.
- `make_kor_img.py`: `*.kor.png`를 원본 IMG와 같은 planar 구조로 변환·압축해 `*.pln.kor.bin`, `*.idx.kor.bin`, `*.kor.IMG`를 생성한다.

세 스크립트 모두 `--workspace`와 `jpn-pc98` 기준의 IMG 상대 경로를 받는다.
