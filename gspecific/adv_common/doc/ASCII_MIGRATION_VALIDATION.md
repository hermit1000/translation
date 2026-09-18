# 구조적 ASCII 추출·번역 이전·출력 검증 개선

2026-09-07. Juice는 문법 참고 자료로만 사용했으며 `gspecific` 하위 코드만 수정했다.

## JSON 생성 규칙

DOB1/DOB2의 `decode_document`와 decoder CLI는 이제 구조적 ASCII 출력을 기본 해석한다.
토큰 경계의 `21 <20..7E 바이트> 00`에서 표시 문자열을 하나의 text로 보존한다.
숫자 한 글자·공백 한 글자도 출력 레코드로 남기며, 공백만 있는 레코드는 기존 lang
초기화의 `strip()` 규칙에 따라 번역 후보 목록에서 제외될 수 있다.

확인하지 않은 비ASCII 혼합·미종결·FF 종료 형식에는 새 규칙을 확대하지 않았다.
따옴표 인자와 이미 소비한 토큰 내부에서 시작점을 검색하지 않는다.
저수준 DOB1/DOB2 `decode_mes`의 기본값은 유지하여 기존 인코더의 명령 해석을 바꾸지 않았다.
Marine의 기존 구조적 ASCII 기본값도 유지한다.

```powershell
python -m gspecific.dob1.adv98_mes.decode_mes INPUT.MES NEW.json
python -m gspecific.dob2.adv98_mes.decode_mes INPUT.MES NEW.json
# 기존 추출 규칙과 비교할 때
python -m gspecific.dob2.adv98_mes.decode_mes INPUT.MES OLD.json --no-structured-ascii
```

DOB1 인코더는 `raw_hex`가 있는 text 레코드에서 원본 바이트를 직접 검증한다.
ASCII의 공백·닫는 괄호를 압축 일본어 규칙으로 재인코딩하다 실패하는 문제를 피한다.
raw_hex가 없는 기존 JSON에는 이전 검증 경로가 유지된다.

## 기존 번역 이전

```powershell
python -m gspecific.adv_common.migrate_ascii dob2 ORIGINAL.MES ORIGINAL.MES_info.json ORIGINAL.MES_lang.json NEW_DIRECTORY
```

첫 인수는 `dob1` 또는 `dob2`다. 새 출력 디렉터리는 기존 info/lang과 분리해야 하며
동일 이름의 결과가 있으면 덮어쓰지 않는다.

- 원본 SHA-256과 info 참조를 검증한다.
- text의 원문·원본 바이트·시작/종료 범위를 비교한다.
- 구형 DOB1 info에 raw_hex가 없으면 해시가 일치한 원본 범위에서 복원한다.
- DOB1 대화 그룹은 연결된 text segment와 화자/매크로 레코드도 비교한다.
- 동일 구간의 번역·상태·사용자 추가 필드는 보존한다.
- 새 미번역 후보는 overlay로 추가한다. 화자를 추정해 새 그룹으로 자동 결합하지 않는다.
- 기존 구간 변경·분할·병합·누락·중복은 `review_required`에 원래 entry 전체와 이유를 남긴다.
- 검토 항목이 하나라도 있으면 **migration_report.json만 쓰고 종료 코드 1**을 반환한다.
  검토가 없으면 새 info/lang도 함께 쓴다. 기존 파일은 수정하지 않는다.

새 보고서의 `changes`는 오프셋별 이전/이후 원문·범위·바이트를 포함한다.
오프셋 이동이나 분할/병합은 여러 변경으로 집계되므로 독립 문장 오류 수가 아니다.

DOB2의 `initialize_translation --force`는 이전 info/lang 쌍과 동일한 보존 검증을 수행한다.
어느 파일이든 검토가 필요하면 기존 파일을 하나도 쓰기 전에 중단한다.
신규 JSON만 별도 생성하려면 다음과 같이 실행한다. 이 옵션 자체는 기존 번역을 이전하지 않는다.

```powershell
python -m gspecific.dob2.adv98_mes.initialize_translation WORKSPACE --output-dir NEW_DIRECTORY
python -m gspecific.marine_philt.adv98_mes.initialize_translation WORKSPACE --output-dir NEW_DIRECTORY
```

## 인코딩 결과 검증

세 게임의 단일 MES encoder는 `--patch-manifest OUTPUT.patches.json`을 지원한다.
배치 encoder의 `--manifest-dir DIR`는 `<원본파일명>.patches.json`을 생성한다.

```powershell
python -m gspecific.dob1.adv98_mes.encode_mes_batch WORKSPACE --no-dosbox-x --manifest-dir MANIFEST_DIRECTORY
python -m gspecific.dob1.adv98_mes.validate_korean_mes WORKSPACE --manifest-dir MANIFEST_DIRECTORY
```

manifest에는 원본/출력 해시와 치환별 source_hex, replacement_hex, 원본 포함 범위가 들어간다.
`text`, `macro`, `adapter` 종류는 인코더가 수행한 일반 번역·매크로 치환·크레디트 재구성을 구분한다.
검증은 각 치환 사이와 파일 끝의 미수정 바이트까지 비교한다. 선언하지 않은 명령 변경,
출력 잘림, 불필요한 바이트 추가, 잘못된 치환 내용, 잘못된 원본을 검출한다.
manifest 검증은 게임별 문자 디코딩을 사용하지 않으므로 DOB2/Marine 출력에도 사용할 수 있다.
위 디렉터리 CLI는 MES를 대상으로 하며 CAL은 Python `verify_patch_manifest`로 검증할 수 있다.

manifest 없이 실행하면 DOB1 lexer의 비텍스트 토큰 종류와 원본 바이트를 비교한다.
따옴표 인자 내부의 `BA 28 xx`를 문장부호 호출로 오인하지 않는다.
합법적인 매크로의 문자 치환도 차이로 보고하므로 실제 번역 검증에는 manifest를 권장한다.
출력 파일 누락과 원본 파일 0개도 실패로 처리한다.

이는 **선언된 변경과 그 밖의 바이트 보존**을 확인하는 검사다.
잘못 선언된 번역 범위의 의미, 분기 주소의 유효성, 화면 표시, 게임 실행까지 증명하지 않는다.

## 이번 검증 결과

- 구조적 ASCII 모드에서 DOB1 82개, DOB2 117개, Marine 134개, 총 333개 MES의 토큰
  연속 범위와 원본 전체 바이트 복원을 확인했다.
- 일회성 CLI 검증: 숫자·공백·문장부호, 인자 내부 오탐 방지, 미종결/비ASCII 입력,
  새/이전 추출 옵션, 동일 번역 이전, 변경 번역 보고서 전용 출력, 재실행 덮어쓰기 거부 통과.
- DOB1/DOB2의 ASCII 원문을 번역해 manifest와 함께 출력하고 미수정 명령 변조·잘림·추가·
  payload 변조를 검출했다. 의도된 DOB1 문장부호 매크로 치환도 manifest 검증을 통과했다.
- DOB2 배치 초기화는 뒤쪽 파일의 변경 범위 발견 시 앞쪽 파일까지 쓰지 않음을 확인했다.
- 기존 실제 info/lang은 메모리에서 비교했고 기존 entry의 번역·상태·추가 필드가 유지됨을 확인했다.

| 게임 | 비교한 기존 info/lang 쌍 | 자동 이전 가능 | 검토 필요 | 원본만 있고 쌍이 없음 |
|---|---:|---:|---:|---:|
| DOB1 | 79 | 66 | 13 | 3 |
| DOB2 | 117 | 116 | 1 | 0 |

DOB1 검토 파일: 000007, 000015, 000030, 000035, 000038, 000039, 000044,
000045, 000046, 000047, 000048, 000049, 000057.MES. 목록의 숫자 파일명은 모두 `.MES`다.
검토 entry는 28개이며, 000038/000039에는 기존 overlay 중복도 있다.
쌍이 없는 파일은 48PLUS.MES, OOOOOO.MES, TOWNS.MES다.
DOB2는 INIT.MES의 entry 1개가 검토 대상이다.

DOB1 변경 범위 3,395개에는 기존 info에서 생략된 레코드와 ASCII 재분할이 포함된다.
DOB2 변경 범위는 6개다. 이 수치를 모두 신규 버그나 독립 번역문 개수로 해석하면 안 된다.
자동 이전 가능 판정은 검토 항목이 없다는 뜻이며 게임 실행 검증을 대체하지 않는다.

실제 게임 MES와 기존 번역 JSON은 쓰지 않았다. 검증용 임시 파일만 사용했다.
