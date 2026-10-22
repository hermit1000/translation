# First Queen PC-98 텍스트 작업

기본 작업폴더는 `C:/work_han/workspace11`입니다. 코드폴더에서 Conda `base` Python으로 실행합니다.

```powershell
C:\Users\hyunx\miniconda3\python.exe -m gspecific.fq.fq1.extract_lang
C:\Users\hyunx\miniconda3\python.exe -m gspecific.fq.fq1.make_dialogue_dictionary
C:\Users\hyunx\miniconda3\python.exe -m gspecific.fq.fq1.apply_dialogue_dictionary --dry-run
C:\Users\hyunx\miniconda3\python.exe -m gspecific.fq.fq1.apply_dialogue_dictionary
C:\Users\hyunx\miniconda3\python.exe -m gspecific.fq.fq1.write_lang
```

`extract_lang`은 원본 D88의 대사, 오프닝, 엔딩, 시스템 문구, 지역명, 아이템명을 `script_init-pc98`에 추출합니다. 편집 중인 `script-pc98/*_lang.json`은 덮어쓰지 않습니다. `CLASS_NAMES`와 `UNIT_NAMES`는 기존 번역 파일을 유지합니다.

`make_dialogue_dictionary`는 디스크 A/B의 모든 `*_lang.json`을 비교해 작업폴더에 `dictionary.json`과 `annoying.json`을 만듭니다. `annoying.json`에서 선택한 번역이 하나인 항목만 `apply_dialogue_dictionary`가 적용합니다. 충돌 목록을 재생성하면 수동 선택값을 다시 확인해야 합니다.

`write_lang`은 원본 D88에 번역을 기록해 `kor-pc98`에 생성합니다. 디스크 A/B의 `SERIFU`는 주소표를 갱신하고, `SERIFU_EXTRA`는 별도 고정 위치에 기록합니다. `ITEM_NAMES`는 주소표와 이름 묶음을 함께 갱신합니다. 인코딩 후 번역 바이트 길이도 갱신합니다.
