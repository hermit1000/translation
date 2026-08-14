# 압축 이미지 변환

이 문서는 이 저장소에서 압축된 게임 이미지를 추출·디코딩하고, PNG를 다시 게임 데이터로 인코딩하는 과정을 설명한다.

Workspace에서는 원본과 한글 이미지 변환 자료를 플랫폼별 `image-<platform>/` 아래에 함께 보관한다.

```text
image-pc98/
image-dos/
```

두 플랫폼은 별도로 디코딩·인코딩하며 중간 파일을 공유하지 않는다.

## 공통 단계와 파일 이름

이미지 변환은 다음 네 가지 표현을 기준으로 한다.

| 단계 | 파일 suffix | 의미 |
| --- | --- | --- |
| Compressed: 전체 파일 | `.jpn.<ext>` / `.kor.<ext>` | 원본 확장자를 보존한 이미지 파일 |
| Compressed: 하위 영역 | `.cmp.jpn.bin` / `.cmp.kor.bin` | 패키지 내부에서 추출한 압축 이미지 block |
| Planar | `.pln.jpn.bin` / `.pln.kor.bin` | 압축 해제된 3bpp/4bpp planar 데이터 |
| Indexed | `.idx.jpn.bin` / `.idx.kor.bin` | 행 우선 픽셀 인덱스. 픽셀당 1바이트 |
| Image | `.jpn.png` / `.kor.png` | 팔레트를 적용한 확인·편집용 이미지 |
| Background | `.bg.png` | 문자와 언어별 요소를 제거한 재사용 배경 이미지 |

파일명 규칙은 다음과 같다.

```text
전체 파일: <original-stem>.<language>.<original-extension>
하위 영역: <offset>.cmp.<language>.bin

<stem>.<stage>.<language>.bin
<stem>.<language>.png
<stem>.bg.png
```

`cmp`, `pln`, `idx`와 `jpn`, `kor`는 모두 3글자로 맞춘다.

```text
000180.cmp.jpn.bin
000180.pln.jpn.bin
000180.idx.jpn.bin
000180.jpn.png

000180.cmp.kor.bin
000180.pln.kor.bin
000180.idx.kor.bin
000180.kor.png

000180.meta.json
```

문자와 언어별 요소를 제거한 배경 파생물은 `<stem>.bg.png`로 저장한다.
배경은 특정 언어 결과물이 아니므로 `jpn` 또는 `kor`를 붙이지 않는다.
`no_text`, `notext`, `kor_no_text`처럼 같은 의미를 나타내는 별도 suffix는
사용하지 않는다.

```text
TITLE.bg.png
END2.bg.png
```

원본 파일 전체가 하나의 이미지이면 compressed 단계에서 `.cmp.bin`을 사용하지 않는다.

```text
END_S3.jpn.DAT
END_S3.kor.DAT

C01_07.jpn.OLH
C01_07.kor.OLH

STR_MENU.jpn.OZM
STR_MENU.kor.OZM
```

원래 확장자의 대소문자도 유지한다. `END_S3.DAT`를 `END_S3.jpn.DAT`로 만드는 방식이며, `END_S3.DAT.jpn.DAT`처럼 확장자를 중복하지 않는다.

Workspace 내부의 전체 경로는 원본 바이너리의 상대 경로와 파일명을 유지한다.

```text
image-pc98/OPEN.DAT/000180.cmp.jpn.bin
image-pc98/OPEN.DAT/000180.cmp.kor.bin

image-dos/DATA/OPEN.DAT/000180.cmp.jpn.bin
image-dos/DATA/OPEN.DAT/000180.cmp.kor.bin
```

여러 파일에서 재사용하는 이미지 블록도 `common/` 같은 별도 디렉터리로
옮기지 않고, 블록을 추출한 기준 원본 파일명과 오프셋을 유지한다.

```text
binary_inputs-pc98/ODAMAIN.EXE/018652.pln.kor.bin
```

전체 파일이 이미지인 경우:

```text
image-pc98/END_S3.DAT/END_S3.jpn.DAT
image-pc98/END_S3.DAT/END_S3.kor.DAT
```

- `jpn`: 원본 게임에서 추출하거나 디코딩한 데이터
- `kor`: 한글 이미지에서 다시 생성하거나 인코딩한 데이터

`pln.jpn.bin`은 공통 layout으로 정규화하지 않고 게임의 원본 planar 배열을 그대로 보존한다. `pln.kor.bin`도 같은 bpp, plane 순서와 layout을 사용한다.

압축되지 않은 이미지는 `cmp` 단계가 없다. 원본 이미지 영역 자체가 planar 데이터이므로 `pln`부터 시작한다. 압축 해제 결과가 planar가 아닌 포맷은 `pln` 단계도 생략할 수 있다.

```text
일반 압축 이미지: cmp → pln → idx → png
비압축 이미지:          pln → idx → png
planar가 없는 코덱: cmp ─────→ idx → png
```

PNG는 팔레트가 적용된 최종 이미지라는 의미로 사용하므로 파일명에 `rgb`를 추가하지 않는다.

## 각 단계의 계약

### `.cmp.<language>.bin`

- `cmp.jpn.bin`은 원본 패키지나 실행 파일에서 추출한 한 이미지의 압축 block이다.
- `cmp.kor.bin`은 한글 이미지를 게임 형식으로 다시 압축한 block이다.
- RLE, LZ 또는 게임 전용 명령 스트림을 포함한다.
- 이미지 block 자체의 크기 헤더 등 디코딩에 필요한 지역 헤더는 포함할 수 있다.
- 여러 이미지가 들어 있는 `.DAT`, `.NPK`, `.EXE` 전체를 의미하지 않는다.
- 압축되지 않은 이미지에는 만들지 않는다.
- 원본 파일 전체가 하나의 이미지이면 이 이름 대신 `.jpn.<원래 확장자>`와 `.kor.<원래 확장자>`를 사용한다.

### `.pln.<language>.bin`

- 압축을 모두 해제한 planar bytes이다.
- 헤더, RLE/LZ 명령 및 패딩은 포함하지 않는다.
- `pln.jpn.bin`은 게임에서 사용하는 원래 plane 순서와 바이트 배열을 변경하지 않는다.
- `pln.kor.bin`은 원본과 같은 구조로 한글 이미지의 픽셀을 배열한다.
- 다른 layout으로 변환한 파생 planar 데이터는 기준 `pln.<language>.bin`으로 저장하지 않는다.
- 3bpp 또는 4bpp와 planar layout 정보가 있어야 해석할 수 있다.
- 대표 layout은 `interleaved`, `plane-major-row`, `plane-major-column`이다.

압축되지 않은 크기는 다음과 같다.

```text
width × height × planes ÷ 8
```

### `.idx.<language>.bin`

- 화면의 왼쪽 위부터 오른쪽 아래까지 행 우선으로 저장한 픽셀 인덱스이다.
- 픽셀 하나를 1바이트로 저장한다.
- 3bpp 이미지는 `0..7`, 4bpp 이미지는 `0..15`만 사용한다.
- 길이는 항상 `width × height`이다.

### `.<language>.png`

- `idx`의 각 값에 팔레트 색상을 적용한 편집·확인용 이미지이다.
- 논리적으로는 RGB 단계지만 PNG 파일 자체는 RGB 또는 indexed PNG일 수 있다.
- 게임 데이터로 되돌릴 때는 RGB를 원래 팔레트의 인덱스로 다시 변환한다.

### `.bg.png`

- 번역문을 합성하기 전의 공통 배경 이미지이다.
- 원본 문자와 언어별 장식 등 교체 대상 요소를 제거한 상태를 저장한다.
- 특정 언어에 종속되지 않으므로 파일명에 `jpn` 또는 `kor`를 넣지 않는다.
- 같은 의미의 파일을 `no_text` 등의 이름으로 중복 보관하지 않는다.
- 게임에 직접 삽입하는 바이너리가 아니라 PNG 편집 과정의 파생 자료이다.

## 메타데이터

확장자는 처리 단계와 언어를 나타낸다. 압축 방식, bpp, layout과 팔레트는 양쪽이 공유하는 같은 stem의 `meta.json`에 기록한다.

```json
{
  "source": "END_S3.DAT",
  "offset": "0x000000",
  "original_size": 28391,
  "encoded_size": null,
  "stored_size": null,
  "padding_byte": null,
  "compression": "garyou-rle",
  "width": 640,
  "height": 400,
  "planes": 4,
  "plane_order": "BRGI",
  "planar_layout": "plane-major-row",
  "bit_order": "msb-first",
  "stride": 80,
  "planar_segments": 2,
  "palette": "ENDPAL.GRG#3"
}
```

필수 정보:

- 원본 파일과 이미지 시작 offset
- `original_size`: 원본 이미지 block이 차지하는 바이트 수
- `encoded_size`: 패딩 전 한글 압축 데이터의 실제 크기
- `stored_size`: 패딩을 포함해 실제로 기록할 한글 압축 데이터의 크기
- `padding_byte`: 고정 영역의 남는 부분을 채울 값. 패딩하지 않으면 `null`
- 압축 방식 또는 `none`
- 너비와 높이
- plane 수
- plane 순서와 bit 순서
- planar layout
- 별도 stride나 화면 분할 방식
- 팔레트 종류 또는 팔레트 파일 위치

`encoded_size`, `stored_size`와 `padding_byte`는 디코딩 직후에는 `null`로 두고 한글 이미지를 인코딩한 뒤 갱신한다. end address는 별도로 저장하지 않고 다음과 같이 계산한다.

```text
원본 영역 = [offset, offset + original_size)
```

고정 영역에 삽입할 때는 다음 조건을 사용한다.

```text
encoded_size > original_size  → 삽입 중단 또는 재배치
encoded_size < original_size  → 필요한 경우 남는 영역 패딩
stored_size == original_size  → 원본 영역에 그대로 덮어쓰기 가능
```

## 디코딩

압축 해제 결과가 원래 planar인 포맷은 다음 순서를 따른다.

```text
원본 package
  ↓ offset/크기로 이미지 영역 추출
cmp.jpn.bin
  ↓ 게임별 RLE/LZ 해제
pln.jpn.bin
  ↓ bpp와 layout에 따라 plane 결합
idx.jpn.bin
  ↓ 팔레트 적용
jpn.png
```

전체 파일이 이미지 포맷이면 첫 단계의 `cmp.jpn.bin` 대신 `END_S3.jpn.DAT`, `MG09.jpn.IMG`, `STR_MENU.jpn.OZM` 같은 네이티브 파일을 사용한다.

각 단계의 책임은 다음과 같이 나뉜다.

1. 이미지 영역 추출: `gspecific`의 파일 목록, offset 및 크기 정의
2. 압축 해제: 각 게임 또는 파일 포맷의 decoder
3. Planar 해제: `module.pc98_image.planar`
4. 팔레트 적용 및 PNG 저장: `module.pc98_image.palette`, `pillow_adapter`

압축 포맷이 픽셀 그룹이나 인덱스를 직접 표현하면 decoder가 `cmp`에서 `idx`를 바로 만든다. 이 경우 기준 `pln.<language>.bin`은 생성하지 않는다.

## 인코딩

원래 planar를 사용하는 포맷의 인코딩은 디코딩의 역순이다.

```text
kor.png
  ↓ RGB를 게임 팔레트에 매핑
idx.kor.bin
  ↓ 지정 layout의 3bpp/4bpp로 분리
pln.kor.bin
  ↓ 게임별 RLE/LZ 압축 및 지역 헤더 생성
cmp.kor.bin
  ↓ 원래 offset에 삽입하거나 package 재구성
게임 데이터
```

전체 파일을 다시 만드는 경우 마지막 `cmp.kor.bin` 대신 `END_S3.kor.DAT`, `MG09.kor.IMG`, `STR_MENU.kor.OZM` 같은 네이티브 파일을 생성한다.

인코딩 시 확인할 사항:

- PNG 크기가 원본 너비·높이와 같은가
- 모든 픽셀이 허용된 팔레트로 변환되는가
- plane 수와 layout이 원본과 같은가
- 새 `cmp`가 원본 영역에 들어가는가
- 고정 영역이면 필요한 길이까지 패딩했는가
- 생성한 `cmp`를 다시 디코딩했을 때 `idx`가 일치하는가

원래 planar 단계가 없는 포맷은 `idx`에서 게임별 압축 표현을 직접 생성한다.

## 저장소의 압축 이미지 형식

| 형식 | 압축 | Planar | 색상 | 구현 |
| --- | --- | --- | --- | --- |
| Taikou 1 RLE/LZ block | 전용 RLE/LZ | 없음: 4픽셀 B/R/G 그룹 | 3bpp, 8색 | `gspecific/taikou1/pc98_image_codec.py` |
| Garyou `END_S*.DAT` | 전용 RLE | plane-major-row | 4bpp, 16색 | `gspecific/garyou/` |
| Mac1 `.IMG` | XOR delta + RLE | plane-major-row | 4bpp, 16 index | `gspecific/mac1/` |
| `.OLH` | 명령 기반 압축 | plane-major-column | 4bpp, 16색 | `module/pc98_image/formats/olh.py` |
| `.OZM` | OZM RLE | plane-major-column | 4bpp, 16색 | `module/pc98_image/formats/ozm.py` |

### Taikou 1 RLE/LZ

대상은 `OPEN.DAT`, `END.DAT`, `GRAPH.DAT`, `EV_PIC.DAT` 내부의 연속 이미지 block이다.

```text
DAT 내부 <width, height> + RLE/LZ block
  → 4픽셀 단위 B/R/G 그룹 해제
  → 3bpp idx
  → 8색 PNG
```

이 코덱은 압축 스트림에서 `idx`를 직접 복원하므로 기준 `pln.<language>.bin`을 만들지 않는다. 현재 코드가 반환하는 `plane.raw`는 복원한 `idx`를 interleaved planar로 다시 인코딩한 파생 데이터이며, 원본 압축 해제 결과가 아니다.

현재 파일명과 새 단계의 대응:

```text
디코더의 *.rle_lz.bin  → *.cmp.jpn.bin
디코더의 *.plane.raw   → 파생 planar이므로 기준 파일에서 제외
디코더의 *.pixels.raw  → *.idx.jpn.bin
*.jpn 폴더의 *.png     → *.jpn.png
*.kor 폴더의 *.png     → *.kor.png
인코더의 *.rle_lz.bin  → *.cmp.kor.bin
*.rle_lz.padded.bin    → *.cmp.kor.bin + meta.json의 padding 정보
```

인코딩 시 PNG를 PC-98 8색에 매핑해 RLE/LZ block을 만든다. 원본 영역에 덮어쓸 때는 원본 압축 크기 이하인지 검사하고, 기본적으로 남는 공간을 `0x00`으로 패딩한다.

### Garyou `END_S*.DAT`

```text
END_Sn.DAT
  → 4바이트 크기 헤더 + RLE 해제
  → 위·아래 640×200의 4bpp plane-major-row
  → 640×400 idx
  → ENDPAL.GRG/BRG의 n번째 팔레트
  → PNG
```

역변환에서는 PNG의 모든 RGB 색상이 해당 팔레트에 정확히 있어야 한다. 두 개의 640×200 planar 영역을 만들고 RLE 압축한 뒤 4바이트 크기 헤더를 붙인다.

`END_Sn.DAT`는 파일 전체가 한 이미지이므로 `END_Sn.jpn.DAT`와 `END_Sn.kor.DAT`로 보관한다. `pln.jpn.bin`은 RLE 해제 후의 128,000바이트 planar 데이터이며, 한글 이미지를 인코딩하면 대응하는 `pln.kor.bin`이 생성된다.

### Mac1 `.IMG`

```text
IMG의 6바이트 헤더 + 압축 payload
  → XOR delta + RLE 해제
  → 4bpp plane-major-row
  → 0..15 idx
  → 현재 구현에서는 회색조 BMP
```

현재 코드는 실제 RGB 팔레트 대신 `index × 17`의 회색조를 사용한다. 이 이미지는 색상 표현보다 인덱스 편집을 위한 것이다.

역변환에서는 회색조 값을 17로 나누어 `idx`를 만들고, planar 변환과 XOR delta/RLE 압축을 수행한 뒤 원본 헤더를 붙인다.

통일 규칙에 맞춰 PNG를 사용하려면 Mac1의 입·출력 코드도 PNG를 읽고 쓰도록 함께 변경해야 한다.

IMG 파일 전체가 한 이미지이므로 네이티브 파일은 `MG09.jpn.IMG`와 `MG09.kor.IMG`처럼 보관한다.

### OLH

```text
OLH 프레임
  → 프레임 헤더, 크기, 선택적 팔레트 해석
  → 명령 기반 압축 해제
  → 4bpp plane-major-column
  → idx
  → PNG
```

OLH는 한 파일에 여러 프레임을 포함할 수 있다. 인코더는 PNG에서 얻은 `idx`를 plane-major-column으로 구성하고 압축한 뒤 프레임 헤더와 팔레트를 기록한다.

프레임별 중간 자료는 offset이나 frame 번호를 stem으로 사용하되, 완성된 OLH 전체 파일은 `C01_07.jpn.OLH`와 `C01_07.kor.OLH`처럼 보관한다.

`module/pc98_image/formats/olh.py`와 `gspecific/mac2/olh.py`에 유사한 구현이 병존한다.

### OZM

```text
OZM
  → 버전, 크기, 데이터 offset, 선택적 팔레트 해석
  → OZM RLE 해제
  → 4bpp plane-major-column
  → idx
  → PNG
```

인코더는 PNG의 RGB를 OZM 팔레트에 매핑하고, 4bpp plane을 만든 뒤 OZM RLE와 헤더를 기록한다.

OZM 파일 전체가 한 이미지이므로 `STR_MENU.jpn.OZM`과 `STR_MENU.kor.OZM`처럼 보관한다.

## 압축되지 않은 이미지

Taikou 1의 `GRAPH.PUT`, `HIME.PUT`, `KAO.PUT`, `PTN.DAT` 및 `MAIN.EXE` 내부 일부 이미지는 압축되지 않은 planar block이다.

```text
원본 package
  ↓ offset/크기로 planar 영역 추출
pln.jpn.bin
  ↓ interleaved 3bpp/4bpp 해제
idx.jpn.bin
  ↓ 기본 PC-98 팔레트 적용
jpn.png
```

이 경우 `.cmp.<language>.bin`을 만들지 않는다. 디코더의 `.plane.raw`는 새 규칙의 `.pln.jpn.bin`, 인코더의 `.plane.raw`는 `.pln.kor.bin`에 해당한다.

## 현재 코드와 명명 규칙

- Garyou, Mac1, Mac2 OLH, Taikou 1 실행 스크립트는 `--workspace`를 받아 `jpn-pc98`과 `image-pc98`을 사용한다.
- 이 스크립트들은 언어별 `.cmp`, `.pln`, `.idx`, PNG와 `meta.json`을 합의한 이름으로 저장한다.
- Mac2 OLH의 workspace 인코딩은 현재 단일 프레임 파일만 지원한다.
- 공용 OZM 클래스는 호출자가 경로를 전달하며 workspace 일괄 실행부는 아직 없다.
- 전체 파일이 이미지인 `.DAT`, `.IMG`, `.OLH`, `.OZM`은 언어 tag만 확장자 앞에 추가하고 원래 확장자를 유지한다.
- 여러 데이터가 들어 있는 `.DAT`, `.NPK`, `.EXE`, `.PUT`의 하위 이미지 영역은 offset 기반 중간 파일로 관리한다.

## Planar 보존 원칙

- `pln.jpn.bin`은 압축 해제 직후의 원본 planar bytes와 byte-for-byte 같아야 한다.
- `pln.kor.bin`은 `pln.jpn.bin`과 같은 크기, plane 순서, layout 및 stride를 사용한다.
- plane 순서, 행·열 우선 방식, stride, 화면 분할을 바꾸지 않는다.
- layout 차이는 파일명에 넣지 않고 `meta.json`에 기록한다.
- 여러 게임의 공통 비교와 PNG 생성은 정규화된 언어별 `idx`를 기준으로 한다.
- `idx.jpn.bin`에서 다시 만든 planar는 검증에 사용할 수 있지만 원본 `pln.jpn.bin`을 대체하지 않는다.
