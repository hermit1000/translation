# workspace5 NB5 이미지 분석

## 확인한 디코더

`MAIN.EXE.asm`의 `sub_1373A`~`sub_138F2`는 `KAO*.NB5` 초상화
디코더이다.

1. 레코드 선두의 little-endian `width`, `height`를 읽는다.
2. `0xFE` escape 기반 byte 반복을 해제한다.
3. 해제한 byte를 상위/하위 nibble 순서로 소비한다.
4. literal 3bpp index 또는 같은 행/이전 행의 1~8픽셀 거리
   back-reference를 복원한다.
5. 게임 메모리에는 `BRG` 순서의 3bpp interleaved planar로 기록한다.

초상화 레코드는 모두 4-byte 경계에 정렬되며 `64×80` header
`40 00 50 00`으로 시작한다.

PNG 확인용 팔레트는 `MAIN.EXE` file offset `0x047536`의 첫 24 bytes를
8색 B/R/G triplet으로 해석해 사용한다. 기본 PC-98 8색보다 초상화의
피부색과 배경색이 자연스럽다.

| 파일 | 확인한 레코드 수 | 상태 |
| --- | ---: | --- |
| `KAO.NB5` | 929 | 추출 지원 |
| `KAO2.NB5` | 128 | 추출 지원 |
| `KAO3.NB5` | 10 | 추출 지원 |
| `NKAO.NB5` | 3 | SOPEN 전용 추가 초상, 별도 추출 지원 |

## KANJI.NB5

`MAIN.EXE.asm`의 `sub_14984`는 파일 전체 `0x1780` bytes를 읽고
32 bytes 간격으로 188개 문자를 등록한다. 각 항목은 `16×16` 1bpp
mask이므로 비압축 planar 이미지로 추출한다.

## SOPEN.NB5

한글 문자 이미지 생성은 코드폴더에서 다음 명령을 실행한다.

```powershell
& C:\Users\hyunx\miniconda3\python.exe -m gspecific.nobu5.make_sopen_graphic
```

`binary_inputs-pc98/SOPEN.NB5/text.json`의 `kor`와 `direction`을 읽어
25개의 `*.bg.png` 및 `*.kor.png`를 만든다. BISCO 비트맵 글꼴을 사용하며
원본 이미지 크기와 indexed 16색 팔레트를 유지한다. 제목은 원본 테두리와
질감을 남기고 일본어 글자색을 제거한다. 흰 바탕 문구는 새 배경에 그린다.
가로 이름은 폭에 맞춰 압축하고, 세로 문구는 오른쪽 열부터 이름·설명을
배치한다. 날짜는 숫자를 한 글자씩 세로로 배치한다.
이 명령은 PNG 생성만 수행한다.

`SOPEN.EXE.asm`의 `sub_10CEF`는 4bpp BRGI interleaved planar를 복원한다.
네 번째 plane은 color index의 bit 3이다. 이전 문서에서 이를 투명 mask로
해석한 내용은 잘못된 것이므로 16색으로 처리해야 한다.

PNG 확인용 팔레트는 `SOPEN.EXE` file offset `0xBA14`의 첫 16개 B/R/G
entry를 사용한다. `SOPEN.NB5`는 SOPEN 실행 파일에서 직접 그리는 자료이므로
MAIN 공통 팔레트로 바꾸지 않는다.

### 2026-10-08 디코더 재검증

다음 압축 명령을 원본 실행 코드에 맞게 수정했다.

- `0x38` literal: header와 달리 payload의 첫 byte가 상위 byte,
  둘째 byte가 하위 byte이다. 기존 구현은 순서를 반대로 읽고 썼다.
- `0x10` shorthand: `v`를 `(v & 0x0F) | ((v & 0xF0) << 4)`로 확장한다.
  기존 구현은 `0x18`과 같은 `<< 8` 처리를 잘못 적용했다.
- 네 번째 plane을 alpha로 제거하지 않고, color index에 `8`을 더하는 비트로 복원한다.

정확성을 확인하려면 Python 디코더와 인코더끼리의 왕복 검사만으로는 부족하다.
두 코드가 같은 잘못된 규칙을 공유하면 왕복 검사를 통과할 수 있다.
작업폴더의 `reverse/verify_sopen_decoder.py`는 Unicorn에서 원본
`SOPEN.EXE sub_10CEF`의 실제 16비트 x86 명령을 실행해 결과를 비교한다.
SOPEN 55개와 NKAO 3개 모두 planar bytes 및 소비한 압축 stream 길이가 완전히 일치했다.
수정 전에는 첫 SOPEN 이미지에서만 27,722개의 planar byte가 달랐다.

수정 후 원본 이미지를 `image-pc98/SOPEN.NB5`와 `image-pc98/NKAO.NB5`에
다시 추출했다. SOPEN PNG는 16색 indexed PNG로 저장해 같은 RGB를 가진
palette index 0과 8도 구별하여 보존한다.
SOPEN 인코더도 같은 native 명령 규칙과 4개 색 plane의 비트 배치로 수정했다.
기존 한글 PNG 5개를 시험 인코딩해 원본 record 공간 안에 들어가는지와
원본 x86 디코더로 정확히 복원되는지를 확인했다. 투명 PNG는 네 번째
색 plane을 alpha로 바꿀 수 없으므로 인코딩 단계에서 거부한다.

검토용 전후 비교는 작업폴더의 `reverse/SOPEN_decode_review/`에 저장했다.
한글 작업 PNG, 기존 삽입용 BIN 및 게임 파일은 이번 재검증에서 덮어쓰지 않았다.
시험 BIN은 해당 검토 폴더의 `*.trial.kor.bin`에만 저장했다.
기존 한글 작업물의 배경·색상이 이전 추출본을 기준으로 만들어졌다면,
수정된 원본 PNG를 기준으로 다시 확인한 후 정식 인코딩을 진행한다.

```powershell
& 'C:\Users\hyunx\miniconda3\python.exe' -X utf8 'C:\work_han\workspace5\reverse\verify_sopen_decoder.py'
```

## NKAO.NB5

`SOPEN.EXE.asm`의 `sub_15A5A`는 초상 번호가 `0x3A2` 이상이면
`NKAO.NB5`를 열고, 내부 테이블 offset/size로 레코드를 읽은 뒤
`sub_10CEF`로 그린다. 따라서 `NKAO.NB5`는 MAIN의 `KAO*.NB5`
nibble 초상 포맷이 아니라, `SOPEN.NB5`와 같은 압축 계열을 쓰는
`SOPEN.EXE` 전용 4bpp 초상 포맷이다. 같은 `sub_10CEF` 복원 루틴을
사용하므로 위의 literal 수정 사항도 적용한다.

파일에는 `64×80` 레코드 3개가 연속 저장되어 있으며 시작 offset은
`0x0000`, `0x0838`, `0x10FE`이다. PNG 확인용 팔레트는 호출 주체가
`SOPEN.EXE`이므로 `SOPEN.EXE` file offset `0xBA14`의 첫 16색 B/R/G
팔레트를 사용한다.

## ITEM.NB5

`MAIN.EXE.asm`의 `sub_13F8C`는 `ITEM.NB5`에서 `index * 0x438` 위치를
seek한 뒤 0x438 bytes를 읽고 `sub_14358`로 그린다. `sub_14358`은
너비 8 tile, 높이 `0x2D` pixel로 `sub_10FFF`에 전달하므로 각 항목은
`64×45` 3bpp interleaved planar 이미지이다.

파일 크기 `0x6DB0`은 `0x438 × 26`과 정확히 일치한다.

PNG 확인용 팔레트는 `PACK.NB5`와 같은 `MAIN.EXE` file offset
`0x047536`의 첫 24 bytes를 8색 B/R/G triplet으로 해석해 사용한다.
기본 PC-98 8색보다 컵, 서적, 병, 두루마리 등 아이템 색감이 게임 자료에
가깝다.

## PACK.NB5

`MAIN.EXE.asm`의 `sub_13EA8`는 `PACK.NB5`의 `bx * 0x200` 위치를 읽고
선두 4 bytes를 little-endian width/height로 해석한 뒤 `sub_11173`으로
그린다. `sub_11173`은 GRPDRVEX `AH=19h` 호출 wrapper이므로
`SLOGO.NB5`와 같은 GRPDRV 압축 이미지로 추출한다.

PNG 확인용 팔레트는 `MAIN.EXE` 파일 offset `0x047536`의 첫 24 bytes를
8색 B/R/G triplet으로 해석해 사용한다. 이 팔레트는 `sub_1401C` 등에서
`sub_11460(0x0F)`을 호출한 뒤 `sub_13EA8`으로 `PACK.NB5` 배경과 메뉴
부품을 그리는 흐름과 시각 확인 결과가 맞는다.

확인된 시작 sector는 다음 27개이다.

```text
000 039 077 0B1 0F3 0F6 0FB 101 10C 117 128 134 144 151
16C 17E 18A 194 19F 1A8 1AF 1B6 1BF 1D1 1E0 1EC 1F7
```

sector-aligned 위치를 무작정 스캔하면 압축 데이터 내부의 false positive가
나오므로, MAIN에서 호출되거나 연속 블록 경계로 확인된 sector만 추출한다.

## 같은 확장자지만 다른 형식인 파일

### GRAPH.NB5 숫자 키패드

`decode_graphics.py`의 `extract_graph_keypad`는 `GRAPH.NB5`의
`0x00585E`부터 `0x0F3C` (3,900) bytes를 추출한다. 크기는 `104×100`,
형식은 비압축 3bpp BRG interleaved planar이다. 숫자 버튼과
`中断`, `取消`, `最大`, `決定` 한자가 같은 이미지에 포함된다.
입력값은 상단의 빈 입력칸 위에 별도로 그려진다.

`MAIN.EXE sub_3AE30`은 `sub_1482A`로 banked 위치 `0x1BE28`에서
`0x0F3C` bytes를 복사하고, `sub_142EE`로 너비 13 tile, 높이 100픽셀로 그린다.
`sub_148C2`가 파일 `0x3296` 이후를 `E000:1860`에 적재하므로,
원본 offset은 `0x3296 + (0x3E28 - 0x1860) = 0x585E`이다.

결과는 `image-pc98/GRAPH.NB5/00585e.*`에 저장한다. 팔레트는 workspace5의
`capture/main_002.raw1.png`와 대조했다. 입력값 영역을 제외한 9,284픽셀의 RGB가
일치하고, planar 재인코딩도 원본과 일치했다. 이 이미지에서 사용되지 않는
palette index 4는 색을 확인하지 못해 검정 placeholder로 두고 메타데이터에 기록한다.
압축되지 않았으므로 기본 출력에서도 `.pln.jpn.bin`은 유지하며,
`.idx.jpn.bin`은 `--all-artifacts`를 지정한 경우에 유지한다.

`make_kor_graphic.py --graph-only`는 준비된 `00585e.bg.png`에 기존 메뉴와 같은
BISCO 글꼴로 중단·취소·최대·결정을 그려 `binary_inputs-pc98/GRAPH.NB5/00585e.kor.png`를 만든다.
`encode_graphics.py`는 이 PNG를 원본과 같은 3,900바이트의 비압축 planar
`00585e.kor.bin`으로 변환하고, 키패드 영역만 교체한 `GRAPH.NB5`도 같은 폴더에 저장한다.
중복된 검정 placeholder인 palette index 4 대신 원본 검정 index 0을 사용한다.

PACK과 동일한 형식의 `script-pc98/GRAPH.NB5_jpn.json` (`{}`) 및
`GRAPH.NB5_kor.json`을 생성하며, `binary_input`의
`0585E=06799` 범위가 `GRAPH.NB5/00585e.kor.bin`을 참조한다.
`--all-artifacts`를 지정하면 `.pln.kor.bin`, `.idx.kor.bin`도 저장한다.

### MAIN.EXE 전투 화면의 날짜 이미지

`capture/main_007.raw1.png` 왼쪽 위의 `年`, `月`, `日`, `時`는
`MAIN.EXE` file offset `0x04F950`의 비압축 이미지에 포함된다.
크기는 `144×16`, 길이는 `0x360` (864) bytes이며, 3bpp BRG interleaved planar이다.
`MAIN.EXE.asm`의 `sub_3E296`과 `sub_22D76`이 `unk_58550`을
`sub_3E02E`로 너비 18 tile, 높이 16픽셀에 그린다. 화면 위치는 `(8, 16)`이다.

원본 추출 자료는 `image-pc98/MAIN.EXE/04f950.*`, 수동 편집 배경은
`binary_inputs-pc98/MAIN.EXE/04f950.bg.png`에 둔다.
다음 코드를 코드폴더에서 Conda base Python으로 실행하면 PACK 메뉴와 동일한
BISCO 글꼴로 `년`, `월`, `일`, `시`를 그려 `04f950.kor.png`를 생성한다.
글자는 이미지 내부의 x=`32, 64, 96, 128`, y=`0`에 배치한다.
일반 BISCO 글자는 16픽셀 너비이며, 각 날짜 표식 뒤의 빈 공간까지 사용해
숫자 표시 영역과 겹치지 않게 한다. PACK 날짜 표기처럼 그림자는 넣지 않는다.

```python
from pathlib import Path

from PIL import Image

from gspecific.nobu5.make_kor_graphic import (
    BISCO_PATH,
    FONT_TABLE_PATH,
    TextPlacement,
    draw_text,
    resolve_windows_path,
)
from module.font_table import FontTable

directory = resolve_windows_path(
    Path("c:/work_han/workspace5/binary_inputs-pc98/MAIN.EXE")
)
font_table = FontTable(FONT_TABLE_PATH)
font_img = Image.open(resolve_windows_path(BISCO_PATH)).convert("1")
canvas = Image.open(directory / "04f950.bg.png").convert("RGB")
if canvas.size != (144, 16):
    raise ValueError(f"Expected 144x16 background, got {canvas.size}")

for text, x in (("년", 32), ("월", 64), ("일", 96), ("시", 128)):
    draw_text(canvas, font_img, font_table, TextPlacement(text, x, 0, shadow=False))

output = directory / "04f950.kor.png"
canvas.save(output)
print(f"Saved {output}")
```

이 코드는 준비한 배경과 숫자 표시 공간을 보존하고, 한글 PNG만 생성한다.
원본 실행 파일은 수정하지 않는다.

`encode_graphics.py`의 `encode_main_date`는 이 PNG를 원본과 같은
864바이트의 `binary_inputs-pc98/MAIN.EXE/04f950.kor.bin`으로 인코딩한다.
기존 `script-pc98/MAIN.EXE_kor.json`의 대사와 다른 삽입 정보를 유지하면서,
`binary_input`에 `"4F950=4FCAF": "MAIN.EXE/04f950.kor.bin"`을 추가한다.
`MAIN.EXE_jpn.json`과 게임 실행 파일은 변경하지 않는다.
`--all-artifacts`를 지정하면 `.pln.kor.bin`, `.idx.kor.bin`도 저장한다.

### 자료별 형식 구분

`.NB5`는 하나의 공통 이미지 codec 이름이 아니라 게임 자료의 공통 확장자이다.
아래 파일을 초상화 decoder에 넣어서는 안 된다.

- `SOPEN.NB5`, `END.DAT`: 선두에 `640×200` 값이 있으나 초상화
  nibble decoder와 명령 형식이 다르다.
- `SLOGO.NB5`: 선두 값은 `208×112`이나 같은 이유로 별도 decoder가 필요하다.
- `GRAPH.NB5`: `sub_148C2`에서 두 영역으로 나누어 직접 메모리/VRAM에 적재한다.
- `H_PARTS.NB5`, `H_KPARTS.NB5`, `H_SHIRO.NB5`, `H_CHIKEI.NB5`,
  `M_PARTS.NB5`, `M_CHIKEI.NB5`: 지도용 tile·부품·지형 자료이다.
- `ANIME.NB5`: UI/animation 합성 자료로 보이며 항목 경계와 투명색
  규칙을 추가 분석해야 한다.
- `SN*.NB5`, `S*T.NB5`, `STR*.NB5`, `BFILE.NB5`: 시나리오/문자열 및
  복합 데이터가 섞여 있어 이미지 archive로 단정하지 않는다.

## 후속 분석 우선순위

1. `END.DAT`의 640×200 화면 decoder
2. 지도 tile 자료의 크기, plane 배치와 합성 규칙
3. `ANIME.NB5`의 animation 항목 경계와 투명색 규칙
