# ADV98 공용 GPC stride XOR 검증

검증일: 2026-10-03

## 원본과 정적 분석

사용자가 제공한 `C:/work_han/workspace`의 실행 파일을 읽고 기존
`reverse_tools/adv98_dec.py`로 TC0 래퍼를 복호화했다. 원본은 수정하지 않았다.
분석 생성물은 `C:/work_han/workspace1/.tmp/common_gpc`에 보관한다.

| 게임 | 복호화 파일 | stride 루틴 파일 오프셋 | 길이 |
| --- | --- | --- | --- |
| DOB1 | ADVBIOS.EXE.dec | 0x24C3 | 60바이트 |
| DOB2 | BRAIN2.OV1.dec | 0x2825 | 60바이트 |
| Marine Philt | MARINE.OV1.dec | 0x2825 | 60바이트 |
| Dracula | ADVBIOS.OVL.dec | 0x2787 | 60바이트 |
| Necronomicon | NECRO.OV1.dec | 0x30E4 | 64바이트 |

첫 네 게임의 stride 루틴 60바이트는 완전히 동일하다.
SHA-256: `546f722c1222ae467270c400b6078c43a8380177bf7aa5255d7a9d6f00d1d2dc`.

Necronomicon은 세그먼트 보존과 작업 버퍼 주소가 다르지만, 다섯 게임의
핵심 XOR 루프 30바이트는 동일하다.
SHA-256: `f577c9cd4cae4745d6c13f60ca4a6f5250fc4a1b0c5ad96bcbd1f58f4a24cb15`.

`ADV98V.OVL`, `BRAIN2.OVL`, `MARINE.OVL`은 함께 조사했으나 위 stride
루틴을 확인한 위치는 각각의 BIOS 실행 모듈이다. 이 결과는 실행 파일
전체 또는 게임의 모든 그래픽 출력 기능이 동일하다는 뜻은 아니다.

## 동작 차이

게임은 AL을 첫 바이트로 한 번만 초기화한다. stride 체인이 끝나면 SI는
다음 체인 시작 위치로 이동하지만 AL은 직전 체인의 마지막 복원값을 유지한다.
다음 체인의 첫 바이트도 이 AL과 XOR한다.

기존 공용 `undo_xor_delta()`는 각 체인을 독립적으로 처리해 경계의 XOR를
누락했다. 이 때문에 잘못된 행 데이터가 후속 행 누적 XOR까지 전파되었다.

## 수정

- 코덱 전체를 `module.pc98_image.formats.adv98_gpc`로 이동했다.
- 공용 `undo_xor_delta()`를 확인된 게임 루틴의 동작으로 수정했다.
- 인코딩은 공용 `encode_gpc()`와 동일 모듈의 역변환 함수를 사용한다.
- 파일 저장과 PNG 매핑은 `module.pc98_image.adv98_artifacts`를 사용한다.
- Dracula의 개별 row decoder 선택을 제거했다.
- Necronomicon도 같은 공용 함수를 가져와 사용한다.
- 이전 `undo_xor_delta_runtime` 이름은 호환 별칭으로 유지한다.
- 공용 `inverse_horizontal_xor()`도 같은 체인 순서와
  누적값의 정확한 역변환으로 수정했다.
- DAC RGB 표현은 stride 루틴과 별개다. 캡처로 검증된 Dracula와
  Necronomicon의 명시적 DAC 팔레트 선택은 유지한다. DOB1/DOB2/Marine
  Philt의 기존 기본 팔레트 표현은 이번 변경에서 바꾸지 않았다.

FRR 인코더의 기존 `runtime_compatibility` 비트 보정 옵션은 이번에
변경하지 않았다. 본 검증은 stride 변환과 그 역변환을 대상으로 한다.
기존 한국어 GPC 바이너리는 재인코딩하지 않았다.

## 검증

`C:/work_han/workspace1/.tmp/compare_adv98_gpc.py`는 복호화한 실제
기계 코드를 Unicorn 16비트 모드에서 실행한다. 각 게임에 대해
width_bytes=1,2,40,52,80과 stride=0,1,2,3,40,80,255를 조합한
35개 입력을 대조한다.

- 수정 전 공용 디코더: 게임당 35개 중 25개 불일치
- 수정 후 공용 디코더: 다섯 게임 총 175개 입력 불일치 0
- 수정 후 인코더 역변환 → 실제 게임 코드 복원: 175개 입력 불일치 0
- 공용 모듈 이동 후 `tests/pc98_image`: 31개 테스트 통과
- Necronomicon TITLE 및 Dracula TITLE2: 새 공용 루틴으로 직접 복원한
  RGB가 각 기준 캡처와 정확히 일치

```powershell
& C:/Users/hyunx/miniconda3/python.exe C:/work_han/workspace1/.tmp/compare_adv98_gpc.py
& C:/Users/hyunx/miniconda3/python.exe -m pytest -p no:cacheprovider tests/pc98_image -q
```

기계 코드 검증 결과는 `.tmp/common_gpc/verification.json`에 저장한다.
