# Workspace 구조

이 문서는 `workspace*` 디렉터리의 공통 구조와 각 경로의 역할을 설명한다.

디렉터리 이름의 `pc98`은 대상 플랫폼을 나타낸다. 자동화 스크립트에서는 이를 `platform` 값으로 구성하므로, 다른 플랫폼을 사용하면 같은 위치에 `jpn-dos`, `script-dos`, `kor-dos`와 같은 이름을 사용할 수 있다.

## 텍스트 작업 흐름

```text
jpn-pc98/
  원본 일본어 바이너리
       │
       ▼ extract_script_auto.py
script_init-pc98/
  자동 추출한 일본어 JSON
       │
       ▼ 대상 선택, 복사 및 번역
script-pc98/
  편집 중인 *_jpn.json + *_kor.json
  custom_char.json / custom_word.json
       │
       │    binary_inputs-pc98/
       │      이미지, 압축 블록 등의 교체 데이터
       │             │
       └─────────────┴──▶ write_script_auto.py
                             │
                             ▼
kor-pc98/
  번역문을 기록한 한국어 바이너리
       │
       ▼ 복사 및 패키징
kor-pc98-dosbox-x/
  에뮬레이터 실행용 전체 게임 디렉터리
```

`script_init-pc98`는 전체 원본에서 자동 추출한 초기 자료이고, `script-pc98`는 실제 번역 대상으로 선별·편집하는 자료이다. 따라서 두 폴더의 파일 수가 달라도 이상이 아니다. `kor-pc98` 역시 수정된 파일만 담을 수 있어 `jpn-pc98`보다 파일 수가 적을 수 있다.

원본 바이너리의 하위 디렉터리는 이후 단계에서도 유지한다. 예를 들어 `jpn-pc98/BTL/FILE.DAT`에서 추출한 파일은 `script_init-pc98/BTL/FILE.DAT_jpn.json`이 되고, 최종 결과는 `kor-pc98/BTL/FILE.DAT`에 기록된다.

## 이미지 작업 흐름

이미지 디코딩·인코딩 자료의 대표 폴더는 `image-<platform>/`으로 한다.

```text
PC-98: image-pc98/
DOS:   image-dos/
```

`decoded`와 `encoded`를 별도 폴더로 나누지 않는다. 같은 이미지의 원본(`jpn`)과 한글(`kor`) 자료 및 공통 `meta.json`을 한 디렉터리에 두어 비교와 재인코딩이 쉽도록 한다.

```text
jpn-pc98/
  원본 일본어 바이너리
       │
       ▼ 이미지 영역 추출 및 디코딩
image-pc98/<원본 상대 경로>/<원본 파일명>/
  000180.cmp.jpn.bin
  000180.pln.jpn.bin
  000180.idx.jpn.bin
  000180.jpn.png
  000180.meta.json
       │
       ▼ PNG 한글화 및 인코딩
  000180.kor.png
  000180.idx.kor.bin
  000180.pln.kor.bin
  000180.cmp.kor.bin
       │
       ▼ 최종 삽입용 block 선택
binary_inputs-pc98/
       │
       ▼ 원본 offset에 기록
kor-pc98/
```

압축되지 않은 이미지는 `cmp` 파일이 없고, 원래 planar 단계가 없는 코덱은 `pln` 파일이 없다. 파일별 압축 방식, 크기, bpp, layout, 팔레트와 원본 영역 크기는 `meta.json`에 기록한다. 세부 규칙은 [이미지 변환 구조](image_conversion.md)를 따른다.

플랫폼이 다르면 같은 원본 파일명과 offset을 사용하더라도 포맷이 다를 수 있으므로 `image-pc98`와 `image-dos` 사이의 중간 파일을 공유하지 않는다.

위 예시는 `OPEN.DAT` 내부 일부 영역이 이미지인 경우이다. 원본 파일 전체가 하나의 이미지 포맷이면 `.cmp.bin`으로 바꾸지 않고 원래 확장자를 유지한다.

```text
image-pc98/END_S3.DAT/
  END_S3.jpn.DAT
  END_S3.pln.jpn.bin
  END_S3.idx.jpn.bin
  END_S3.jpn.png
  END_S3.bg.png
  END_S3.meta.json
  END_S3.kor.png
  END_S3.idx.kor.bin
  END_S3.pln.kor.bin
  END_S3.kor.DAT
```

즉, 전체 파일은 `<원래 stem>.<language>.<원래 확장자>`, 하위 영역은 `<offset>.cmp.<language>.bin` 형식을 사용한다.

문자와 언어별 요소를 제거한 공통 배경 PNG는 `<stem>.bg.png`로 저장한다.
배경에는 언어 suffix를 붙이지 않으며, `no_text` 대신 항상 `bg`를 사용한다.

```text
binary_inputs-pc98/
  ODAMAIN.EXE/
    018652.kor.png
    018652.pln.kor.bin
  TITLE.PAK/
    TITLE.bg.png
    TITLE.kor.png
    TITLE.kor.PAK
  END2.PAK/
    END2.bg.png
    END2.kor.png
    END2.kor.PAK
```

원본 파일별 디렉터리는 `<원본 파일명>/`을 사용하며
`TITLE.PAK.kor/`처럼 디렉터리명에 언어 suffix를 추가하지 않는다.
여러 대상 파일에 같은 블록을 삽입하더라도 해당 블록을 추출한 기준 원본의
파일명을 사용한다. 따라서 `common/` 같은 용도 중심 이름 대신
`ODAMAIN.EXE/018652.pln.kor.bin`처럼 출처와 오프셋을 보존한다.

## 디렉터리와 파일 설명

| 경로 | 용도 |
| --- | --- |
| `jpn-pc98/` | 패치의 기준이 되는 일본어 원본 바이너리. 쓰기 단계에서 이 파일을 복사해 번역문을 반영한다. |
| `script_init-pc98/` | 원본 바이너리에서 자동 추출한 `*_jpn.json`. 번역 대상을 정하기 전의 초기 결과이다. |
| `script-pc98/` | 실제 작업본. 일반적으로 원본용 `*_jpn.json`과 번역용 `*_kor.json`을 함께 둔다. |
| `kor-pc98/` | `script-pc98`의 번역을 원본 바이너리에 기록한 결과물. |
| `image-pc98/` | PC-98 이미지의 원본·한글 디코딩/인코딩 자료와 메타데이터. |
| `image-dos/` | DOS 이미지의 원본·한글 디코딩/인코딩 자료와 메타데이터. |
| `binary_inputs-pc98/` | JSON 문자열만으로 넣을 수 없는 이미지, 압축 블록, 원시 플래너 데이터 등 바이너리 교체 자료. |
| `kor-pc98-dosbox-x/` | DOSBox-X에서 바로 실행하기 위한 전체 한국어판 파일 트리. 작업 공간에 따라 이름 끝에 `_`가 붙거나 별도 복사본이 존재한다. |
| `reverse/` | 디스어셈블 결과, 포맷 분석 코드, 디코딩 이미지 등 역공학 자료. |
| `capture/` | 실행 화면 캡처 및 확인 자료. |
| `dictionary.json` | 일본어 문장별 번역 후보와 사용 횟수를 모은 대사 사전. |
| `annoying.json` | 동일 일본어에 여러 번역이 사용되는 등 별도 확인이 필요한 문장 목록. |
| `info.txt` | 주소, 용어, 파일 포맷 등 작업 중 발견한 수동 메모. |
| `*.pkl` | 폰트 테이블과 커스텀 문자 조합으로 만든 캐시. 원본 데이터가 아니라 재생성 가능한 가속용 파일이다. |
| `*.bmp` | 한국어 글꼴 캔버스 또는 에뮬레이터용 글꼴 이미지. |
| `*.bat`, `*.conf` | 게임 실행용 배치 파일과 DOSBox-X 설정. |

`script-pc98/custom_char.json`은 기본 폰트 테이블에 없는 문자 매핑을, `custom_word.json`은 여러 글자를 하나의 게임 코드로 취급하는 커스텀 단어 매핑을 제공한다.

## 스크립트 파일 규칙

- `<파일명>_jpn.json`: 원본 바이너리에서 추출한 일본어 문자열과 주소 범위이다. 바이너리 검증과 한국어 기록의 기준으로 사용한다.
- `<파일명>_kor.json`: 같은 주소에 기록할 한국어 번역이다. 대응하는 `_jpn.json`과 한 쌍으로 관리한다.
- JSON 파일의 상대 경로와 `_jpn` 또는 `_kor` 앞의 파일명은 원본 바이너리의 상대 경로 및 파일명과 같아야 한다.
- `script_init-pc98`는 재추출 가능한 초기 산출물이고, 실제 번역 작업의 기준은 `script-pc98`이다.

## 수동 편집 대상과 생성물

| 구분 | 경로 |
| --- | --- |
| 보존할 원본 | `jpn-pc98/` |
| 주로 수동 편집 | `script-pc98/*_kor.json`, `custom_char.json`, `custom_word.json`, `image-<platform>/**/*.kor.png`, `binary_inputs-<platform>/**/*.kor.png`, `binary_inputs-<platform>/**/*.bg.png` |
| 원문·주소 조정 시 함께 편집 | `script-pc98/*_jpn.json` |
| 자동 생성 가능 | `script_init-pc98/`, `image-<platform>/**/*.bin`, `*.jpn.png`, `*.meta.json`, `kor-pc98/`, 폰트 테이블 캐시 `*.pkl` |
| 최종 삽입 입력 | `binary_inputs-pc98/` |
| 실행 테스트용 | `kor-pc98-dosbox-x/` |
| 배포용 패치 | `kor-pc98/` |

## 작업 시 주의사항

- Python 스크립트는 Conda `base` 환경을 사용해 실행한다.
- 문서, JSON, Python 소스(`*.py`)를 포함한 모든 텍스트 파일은 CRLF 줄바꿈 형식으로 저장한다.
- 자동화 스크립트의 `ws_num`, `platform` 값이 코드에 고정된 경우가 많다. 실행 전에 대상 workspace와 `pc98`/`dos` 설정을 확인해야 한다.
- `script-pc98`에서 `*_kor.json`만 수정하더라도 같은 이름의 `*_jpn.json` 주소 범위가 기준이 되므로 두 파일을 쌍으로 관리해야 한다.
- `write_script_auto.py`는 `jpn-pc98`의 원본을 읽어 `kor-pc98`에 쓴다. `kor-pc98`의 기존 파일을 원본처럼 사용하지 않는다.
- `binary_inputs-pc98`의 파일명과 상대 경로는 스크립트 토큰에서 참조될 수 있으므로 임의로 바꾸지 않는다.
- `image-<platform>`은 변환 과정 전체를 보관한다. `binary_inputs-<platform>`에는 실제 기록할 최종 바이너리와 이를 재생성하는 데 필요한 수동 편집 PNG만 두며, 재생성 가능한 일본어·중간 바이너리는 복사하지 않는다.
- `image-pc98`와 `image-dos`는 bpp나 layout이 같아 보여도 플랫폼별로 독립적으로 생성한다.
- `script_init-pc98`, `reverse`, 배포 압축 파일은 목적이 서로 다르다. 번역 작업본은 `script-pc98`, 생성 결과는 `kor-pc98`을 기준으로 판단한다.
- 생성 스크립트를 다시 실행하면 `script_init-pc98`와 `kor-pc98`의 기존 파일을 덮어쓸 수 있으므로, 수동 수정 사항을 생성물에만 남기지 않는다.
