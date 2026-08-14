# mac2 Python 스크립트

- `olh.py`: Macintosh 게임의 OLH 이미지 형식을 읽고 프레임, 크기, 팔레트와 압축 데이터를 해석하는 `OLH` 클래스를 제공한다. 프레임 PNG 저장과 OLH 재압축도 지원하며, Pillow가 없으면 PNG 관련 기능만 사용할 수 없다.

`decode` 또는 `encode` action과 `--workspace`를 지정하면 `jpn-pc98`의 OLH를 파일별 `image-pc98` 폴더에서 변환할 수 있다. 다중 프레임 디코딩은 지원하지만 현재 workspace 인코딩은 단일 프레임만 지원한다.
