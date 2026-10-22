# First Queen II PC-98 복원 도구

기본 작업폴더는 `C:/work_han/workspace12`입니다. 코드폴더에서 Conda `base` Python으로 실행합니다.

```powershell
C:\Users\hyunx\miniconda3\python.exe -m gspecific.fq.fq2.extract_lang
C:\Users\hyunx\miniconda3\python.exe -m gspecific.fq.fq2.make_dialogue_dictionary
C:\Users\hyunx\miniconda3\python.exe -m gspecific.fq.fq2.apply_dialogue_dictionary --dry-run
C:\Users\hyunx\miniconda3\python.exe -m gspecific.fq.fq2.apply_dialogue_dictionary
C:\Users\hyunx\miniconda3\python.exe -m gspecific.fq.fq2.write_lang
```

`extract_lang`은 현재 `script-pc98/*_lang.json`에 기록된 원본 위치와 원본 바이트를 D88 이미지에 대조하고, 번역을 뺀 사본을 `script_init-pc98`에 만듭니다. 원본 바이너리만 스캔하여 새 위치를 찾는 도구는 아닙니다.

`make_dialogue_dictionary`는 세 디스크의 같은 일본어 문장에 사용된 번역을 모아 작업폴더의 `dictionary.json`, `annoying.json`에 기록합니다. 기존 파일이 있으면 덮어쓰므로 편집본은 먼저 보관해야 합니다.

`apply_dialogue_dictionary`는 `annoying.json`의 `translated` 목록에 한 번역만 남긴 문장을 같은 원문 항목에 적용합니다. `--dry-run`으로 적용 대상을 먼저 확인할 수 있습니다.

`write_lang`은 `jpn-pc98` 원본 디스크를 복사하고 `script-pc98/*_lang.json`의 번역을 직접 인코딩합니다. 일반 문자는 코드폴더의 `font_table/font_table-kor-jin.json`, 이름의 `{...}` 토큰은 작업폴더의 `script-pc98/custom_word.json`을 사용합니다. `SERIFU`는 주소표와 본문을 다시 배치합니다. 별도의 `.z` 데이터는 사용하지 않습니다.

현재 JSON으로 만든 세 디스크는 기존 한글 디스크와 SHA-256까지 일치합니다. 오프닝과 A의 일부 대사는 같은 번역 문자열에서도 공백 제거 위치를 자동으로 확정할 수 없어, 해당 JSON 항목에 `wrap_space_indices`와 `wrap_text_sha256`를 기록했습니다. 번역 문자열이 바뀌면 기존 공백 위치는 사용하지 않고 36바이트 줄 경계 규칙으로 다시 인코딩합니다. 새로 편집한 대사는 실제 게임 화면에서 줄 배치를 확인해야 합니다.
