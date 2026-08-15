# 한국어 게임 번역 도구

일본어 고전 게임의 스크립트와 이미지를 추출하고, 한국어로 번역한 뒤 게임
바이너리에 다시 기록하는 Python 도구 모음입니다.

주요 기능은 다음과 같습니다.

- 게임 바이너리에서 일본어 스크립트 추출
- 번역한 한국어 스크립트를 원본 주소에 기록
- PC-98 및 DOS 게임 이미지 디코딩·인코딩
- 게임별 폰트 테이블과 압축 형식 처리
- 인명·지명·아이템 표기를 통일하기 위한 데이터베이스 제공

## 시작하기 전에

이 저장소에는 변환 도구와 공용 데이터가 들어 있습니다. 실제 게임 파일과
번역 작업물은 저장소 옆의 별도 `workspace<N>` 디렉터리에 둡니다.

```text
상위 디렉터리/
├── translation/       이 저장소
└── workspace1/        게임 파일과 번역 작업물
```

자동화 스크립트를 실행하기 전에 각 스크립트의 `main()` 함수 상단에서 다음
값을 작업 대상에 맞게 설정해야 합니다.

- `ws_num`: workspace 번호(예: `1` → `workspace1`)
- `platform`: 대상 플랫폼(`pc98` 또는 `dos`)

Python 3.9 이상이 필요합니다.

## 빠른 시작

### 1. 도구 설치

```bash
git clone git@github:ybaik/translation.git
cd translation
python -m pip install -e .
```

### 2. 원본 게임 파일 준비

원본 게임 바이너리를 상대 경로를 유지한 채 다음 위치에 배치합니다.

```text
workspace<N>/jpn-<platform>/
```

예를 들어 PC-98용 `workspace1`이라면 다음과 같습니다.

```text
workspace1/jpn-pc98/
```

### 3. 일본어 스크립트 추출

`extract_script_auto.py`의 `ws_num`과 `platform`을 설정한 뒤 실행합니다.

```bash
python extract_script_auto.py
```

추출 결과는 `workspace<N>/script_init-<platform>/`에 생성됩니다.

### 4. 번역 파일 만들기

번역할 `*_jpn.json` 파일을 상대 경로 그대로 `script-<platform>/`에 복사하고,
같은 위치에 짝이 되는 `*_kor.json` 파일을 만듭니다.

```text
script-pc98/
├── FILE.DAT_jpn.json   일본어 원문과 주소 정보
└── FILE.DAT_kor.json   한국어 번역문
```

번역문은 원본 주소의 바이트 길이, 제어 코드와 지원 문자를 정확히 지켜야
합니다. 실제 번역을 시작하기 전에
[번역 지침과 검증 규칙](doc/translation_strategy.md)을 반드시 확인하세요.

### 5. 한국어 바이너리 생성

`write_script_auto.py`에도 같은 `ws_num`과 `platform`을 설정한 뒤 실행합니다.

```bash
python write_script_auto.py
```

완성된 파일은 `workspace<N>/kor-<platform>/`에 생성됩니다. 빌드할 때마다
`jpn-<platform>/`의 원본을 기준으로 하므로, `kor-<platform>/`의 결과물을
다음 빌드의 원본으로 사용하지 마세요.

## 전체 작업 흐름

```text
jpn-<platform>/
  원본 게임 바이너리
       ↓ extract_script_auto.py
script_init-<platform>/
  자동 추출된 일본어 JSON
       ↓ 번역 대상 선별
script-<platform>/
  *_jpn.json + *_kor.json
       ↓ write_script_auto.py
kor-<platform>/
  한국어가 기록된 게임 바이너리
```

`script_init-<platform>/`은 다시 생성할 수 있는 초기 추출 결과이고,
`script-<platform>/`이 실제 번역 작업 공간입니다.

스크립트별 추가 매핑이 필요하면 다음 파일을 `script-<platform>/`에 둡니다.

- `custom_char.json`: 원본과 출력 폰트 테이블이 공유하는 문자 코드 재정의
- `custom_word.json`: 한국어 바이트 치환 및 사용자 정의 1바이트 시퀀스

스크립트 메타데이터에서 참조하는 이미지나 압축 블록 등의 교체 자료는
`binary_inputs-<platform>/`에 둡니다.

디렉터리별 역할과 생성물에 관한 자세한 내용은
[Workspace 구조](doc/workspace_structure.md)를 참고하세요.

## 이미지 번역

이미지 작업 자료는 플랫폼별로 분리합니다.

```text
PC-98: image-pc98/
DOS:   image-dos/
```

두 플랫폼의 중간 파일은 서로 공유하지 않습니다. 이미지 파일명, 메타데이터,
디코딩·인코딩 단계, 팔레트와 지원 형식은
[이미지 변환 과정과 형식](doc/image_conversion.md)을 참고하세요.

## 개발 환경 설정

코드를 수정하거나 저장소 개발에 참여하려면 개발용 의존성을 설치합니다.

```bash
python -m pip install -e ".[dev]"
```

이 명령은 실행 의존성(`fonttools`, `numpy`, `pillow`, `opencv-python`, `rich`)과
개발 도구(`pytest`, `ruff`, `pre-commit`)를 함께 설치합니다.

Git pre-commit 훅을 설치하고 검사하려면 다음 명령을 실행합니다.

```bash
python -m pre_commit install --install-hooks
python -m pre_commit run --all-files
```

`git commit`에 사용하는 것과 같은 Python 환경 및 셸에서 훅을 설치해야
합니다. 예를 들어 Windows Git Bash에서 커밋한다면 WSL이 아닌 Windows Git
Bash에서 설치하세요.

## 프로젝트 구조

- `module/`: 핵심 스크립트, 폰트 테이블, 압축 및 이미지 코덱
- `gspecific/`: 게임별 코덱과 변환 도구
- `tools*/`: 분석, 편집, 폰트, 이미지 및 검증 도구
- `font_table/`: 공용 일본어·한국어 문자 테이블
- `name_db/`: 인명, 지역 및 아이템 이름 데이터베이스
- `tests/`: 코덱과 데이터베이스 자동화 테스트
- `doc/`: Workspace, 번역 및 이미지 작업 흐름 문서

## 상세 문서

- [Workspace 구조와 생성 파일](doc/workspace_structure.md)
- [번역 지침과 검증 규칙](doc/translation_strategy.md)
- [이미지 변환 과정과 형식](doc/image_conversion.md)
- [일본 인명 한글 표기 규칙](doc/japanese_name_translation_rules.md)

## 라이선스

MIT License
