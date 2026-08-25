# Dead of the Brain ADV98 reverse tools

ADV98 실행 파일의 복호화·언팩·디스어셈블에 사용한 재현 가능한 분석
도구입니다. 이미지 및 MES 번역 빌드에는 직접 사용되지 않습니다.

- `adv98_dec.py`: TC0 래퍼가 적용된 MZ 실행 파일 복호화
- `unpack_adv98_runtime.py`: Unicorn으로 self-extractor를 실행하고 64 KiB image dump
- `disasm_mz16.py`: MZ load image 또는 raw 16비트 코드 선형 디스어셈블

## 예시

```powershell
python gspecific/dob1/reverse_tools/adv98_dec.py INPUT.EXE OUTPUT.EXE
python gspecific/dob1/reverse_tools/unpack_adv98_runtime.py INPUT.EXE OUTPUT.RAW
python gspecific/dob1/reverse_tools/disasm_mz16.py OUTPUT.RAW --raw
```

`disasm_mz16.py`는 `capstone`, `unpack_adv98_runtime.py`는 `unicorn` 패키지가
필요합니다.
