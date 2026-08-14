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

`SOPEN.EXE.asm`의 `sub_10CEF`는 3bpp color index와 mask plane을 함께
복원한다. 4번째 plane은 색 plane이 아니라 투명 mask로 보아야 하며,
`009e42` 제목 박스 같은 작은 이미지들은 배경 위에 합성되어 최종 화면이
된다. 따라서 단독 PNG는 alpha가 들어간 레이어 이미지이고, 캡처 화면과
완전히 같은 색/배경으로 보려면 실제 그리기 순서대로 합성해야 한다.

PNG 확인용 팔레트는 `SOPEN.EXE` file offset `0xBA14`의 첫 8개 B/R/G
entry를 사용한다. `SOPEN.NB5`는 SOPEN 실행 파일에서 직접 그리는 자료이므로
MAIN 공통 팔레트로 바꾸지 않는다.

## NKAO.NB5

`SOPEN.EXE.asm`의 `sub_15A5A`는 초상 번호가 `0x3A2` 이상이면
`NKAO.NB5`를 열고, 내부 테이블 offset/size로 레코드를 읽은 뒤
`sub_10CEF`로 그린다. 따라서 `NKAO.NB5`는 MAIN의 `KAO*.NB5`
nibble 초상 포맷이 아니라, `SOPEN.NB5`와 같은 압축 계열을 쓰는
`SOPEN.EXE` 전용 4bpp 초상 포맷으로 보는 쪽이 맞다. 현재 추출본을
alpha/mask 레이어로 해석하는 것보다 4bpp 색상으로 복원했을 때 얼굴,
피부색, 음영이 더 자연스럽다.

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
