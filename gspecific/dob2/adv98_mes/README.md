# Dead of the Brain 2 ADV98 MES

DOB2 PC-98판의 ADV98 MES를 분석하고 번역하기 위한 게임 전용 코드입니다.
DOB1과 기본 토큰 구조는 공유하지만, DOB2는 압축 히라가나와 실제 ASCII
문자열이 같은 바이트 범위를 사용하므로 별도의 디코더가 필요합니다.

현재 `decode_mes.py`는 다음을 지원합니다.

- MES 전체 바이트의 무손실 lexical tokenization 검증
- 일반 Shift-JIS와 ADV98 압축 히라가나
- 명백하게 구분되는 DOB2 ASCII 영문 문자열
- CP932로 표현되지 않는 `EBxx` 외자의 비편집 `gaiji` 토큰 보존
- 단일 파일 및 디렉터리 일괄 JSON 추출

아직 DOB2 명령표, 외자 글리프 매핑과 재인코딩은 확정되지 않았습니다.

```powershell
python -m gspecific.dob2.adv98_mes.decode_mes `
  C:\work_han\workspace1\jpn-pc98\MES `
  C:\work_han\workspace1\script_init-pc98\MES
```

기존 파일을 다시 생성하려면 `--force`를 추가합니다.

## 번역 작업 파일 초기화

```powershell
python -m gspecific.dob2.adv98_mes.initialize_translation `
  C:\work_han\workspace1
```

`script-pc98/MES`에 각 MES의 `*_info.json`과 `*_lang.json`을 만듭니다.
DOB2는 DOB1과 달리 화자와 문장부호를 MES에 일반 문자로 직접 기록합니다.
따라서 가상의 `{}` 제어 표기를 만들지 않고 원본 형식을 그대로 사용합니다.
화자형 텍스트는 `dialogue_groups`, 화자가 없는 화면·연출 문자열은
`overlay_texts`에 분리합니다.

```json
{
  "original": "［コール］悪いな、後片付けなんかさせちゃって・・・。",
  "translation": "〔콜〕미안해, 뒷정리까지 시켜서……."
}
```

원작의 전각 대괄호 `［...］`는 현재 한글 폰트표에 없으므로 번역에는
지원되는 `〔...〕`를 사용합니다. `speaker_dictionary.json`은 화자 번역
참고 자료일 뿐 제어 코드나 자동 치환표가 아닙니다.

## 단일 MES 인코딩

```powershell
python -m gspecific.dob2.adv98_mes.encode_mes `
  C:\work_han\workspace1\jpn-pc98\MES\INIT.MES `
  C:\work_han\workspace1\script-pc98\MES\INIT.MES_info.json `
  C:\work_han\workspace1\script-pc98\MES\INIT.MES_lang.json `
  C:\work_han\workspace1\kor-pc98\MES\INIT.MES
```

빈 번역은 원본 바이트를 그대로 보존합니다. 번역을 입력한 레코드만 한글
폰트 코드로 바꾸며, 원문 해시와 각 레코드의 원본 바이트를 모두 검증합니다.
인코딩할 때 표시 위치 31, 61, ...에 놓인 일반 공백은 MES 결과에서만
자동 제거하며 `*_lang.json`의 번역문은 수정하지 않습니다.

## 대사 사전

```powershell
python -m gspecific.dob2.adv98_mes.make_dialogue_dictionary
python -m gspecific.dob2.adv98_mes.apply_dialogue_dictionary --dry-run
python -m gspecific.dob2.adv98_mes.apply_dialogue_dictionary
python -m gspecific.dob2.adv98_mes.apply_dialogue_dictionary --dictionary C:\work_han\workspace1\dictionary.json
```

기본 작업공간은 `C:\work_han\workspace1`입니다. DOB2에서는
`dialogue_groups`와 `overlay_texts`를 모두 대상으로 하며 `@keep`도
보존합니다. 기본 적용 파일은 수동 검토용 `annoying.json`입니다. 전체
`dictionary.json`을 적용하려면 `--dictionary`로 명시해야 합니다. 번역
후보가 하나인 항목만 자동 적용되며, 빈 항목만 채우려면 `--only-empty`를
사용합니다.

검토하기 쉽도록 `annoying.json`에는 원문과 `translated` 후보만 기록합니다.
출현 횟수와 파일·ID 참조 목록은 `dictionary.json`에 보존됩니다.

빈 `translation`도 사전 후보로 기록합니다. 따라서 같은 원문에 빈 번역과
`@keep` 또는 한글 번역이 함께 있으면 `annoying.json`에서 검토할 수
있습니다. 빈 문자열만 있는 원문은 자동 적용하지 않습니다.
