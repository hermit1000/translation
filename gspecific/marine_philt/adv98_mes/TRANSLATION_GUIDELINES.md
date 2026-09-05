# Marine Philt MES 번역 지침

이 문서는 `workspace4/script-pc98/MES/*_lang.json`의 Marine Philt 번역에 적용한다.

## 편집 대상

- `dialogue_groups`와 `overlay_texts` 항목의 `translation`만 번역한다.
- `original`, `id`, `offset`, `source_info`, `format`은 변경하지 않는다.
- 화자명은 `gspecific/marine_philt/speaker_dictionary.json`의 표기를 따른다.
- 번역이 완료되고 검증된 항목의 `status`는 `passed`로 둔다.

## 분할된 문장

MES 원문 한 문장이 여러 레코드로 나뉠 수 있다. 이 경우 각 레코드를 독립된 문장으로 번역하지 말고, 앞뒤 `original`을 이어서 문맥을 확인한다.

- 번역문도 같은 레코드 경계를 유지한다.
- 앞 레코드가 단어 중간에서 끝나면 뒤 레코드가 자연스럽게 이어지도록 번역한다.
- 레코드 경계에 불필요한 공백을 넣지 않는다.

## 구두점과 공백

- 대화창은 한 줄 27자이므로 1-based 28·55번째(0-based 27·54번째)에 해당하는 줄 경계 공백을 넣지 않는다. 인코더도 이 위치의 공백을 자동 제거한다.
- 각 `translation` 항목은 대화창 3줄을 넘기지 않도록 최대 27×3=81자로 작성한다. 81자를 초과할 경우 의미를 유지하면서 문장을 축약한다.
- `.`와 `,` 뒤에는 공백을 넣지 않는다.
- 화자 닫는 괄호 `]` 바로 뒤에 공백을 넣지 않는다. 예: `[시드]아니...`
- `?`와 `!` 뒤에 다음 문장이 이어질 때는 공백을 넣는다.
- 말줄임표 뒤에 새 문장이 이어질 때는 공백을 넣는다.
- 문장 끝이나 레코드 경계에는 불필요한 후행 공백을 넣지 않는다.
- 번역 완료 후 정규식 `[.,] +`에 일치하는 부분이 없는지 검사한다.

## 원문 유지

번역하거나 다시 입력할 필요가 없는 텍스트는 `translation`에 `@keep`을 사용한다.

- `LOAD`, `SAVE`, `SYSTEM`, `[CANCEL]`처럼 그대로 표시할 영문 시스템 문자열
- 공백과 점만으로 이루어진 연출용 문자열
- 원문 바이트를 그대로 보존해야 하는 장식 문자열

`@keep`은 화면에 출력되는 번역문이 아니라 인코더에 원문 바이트 보존을 지시하는 값이다.

## 문자와 인코딩

- 번역문에는 선택한 한글 폰트 테이블에 존재하는 문자만 사용한다.
- JSON 파일은 UTF-8과 CRLF 줄바꿈을 유지한다.
- 작업 후 `encode_mes.py` 또는 `encode_mes_batch.py`로 실제 MES 인코딩을 검증한다.

## TCM DAT 텍스트

`TCM/OPEN.DAT` 같은 오프닝 설명문은 MES가 아닌 줄 단위 CP932 텍스트다. 다음 도구로 동일한 JSON 번역 흐름을 사용한다.

- `initialize_dat_translation.py`: `script-pc98/TCM/*_info.json`과 `*_lang.json` 생성
- `encode_dat.py`: 한 DAT 파일의 번역문을 적용
- `encode_dat_batch.py`: `script-pc98/TCM/*_lang.json`을 찾아 일괄 적용

DAT는 각 줄의 원본 표시 글자 수가 화면 배치를 결정하므로 `display_cells`와 번역문의 글자 수가 정확히 같아야 한다. 길이가 다르면 인코더가 오류로 중단한다. `OPEN.DAT`의 번역 JSON은 `script-pc98/TCM/OPEN.DAT_lang.json`이다.
- 모든 번역 항목이 `passed`인지 확인한다.

## 최종 점검

1. 분할된 원문과 번역문을 앞뒤로 이어 읽는다.
2. 화자명이 `speaker_dictionary.json`과 일치하는지 확인한다.
3. `.`와 `,` 뒤의 공백 및 레코드 경계의 불필요한 공백을 제거한다.
4. 원문 유지 항목이 `@keep`인지 확인한다.
5. 실제 MES 인코딩이 오류 없이 완료되는지 확인한다.
