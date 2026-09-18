# DOS/PC-98 16비트 바이너리 정적·동적 분석 가이드

이 문서는 PC-98/DOS 게임의 실행 파일, 오버레이, 스크립트, 리소스 파일을 분석할 때 재사용하기 위한 절차를 정리한 문서다.

## 권장 도구 조합

### disasm_mz16.py

`disasm_mz16.py`는 8086/16비트 raw 바이너리를 빠르게 선형 disassemble하는 보조 도구다.

- 압축 해제 후 진입점 검증
- raw offset과 runtime offset 대응 확인
- 특정 주소 주변 명령어 확인
- Cutter/IDA 자동 분석 결과의 1차 검증

사용 예:

```powershell
python disasm_mz16.py GAME.OV1.dec.raw --raw --offset 17CC --length 800
python disasm_mz16.py GAME.OVL.dec.raw --raw --offset E000 --length 1000
```

전체 파일을 선형 disassemble하면 문자열과 데이터도 명령어처럼 표시될 수 있으므로, 함수 구조를 확정하는 용도로 사용하지 않는다.

### Cutter 2.4.1

Cutter는 Rizin 기반의 대화형 정적 분석 도구다. Windows 파일명이 `x86_64`인 것은 Cutter 자체가 64비트라는 뜻이며, 분석 대상은 별도로 16비트 x86으로 설정할 수 있다.

- Architecture: `x86`
- Bits: `16`
- Base address: `0`
- raw 이미지의 실제 진입점으로 이동 후 함수 생성

Rizin 콘솔 예:

```text
e asm.arch=x86
e asm.bits=16
s 0x17cc
af
pdf
```

### IDA64 7.7

IDA는 Cutter에서 찾은 주소를 정밀하게 분석할 때 사용한다.

- 함수 생성과 이름 지정
- 호출 그래프와 분기 그래프 확인
- 데이터 구조와 버퍼에 주석 추가
- 제어코드 비교 지점의 호출자/피호출자 추적

raw 바이너리 로드 설정:

- File type: `Raw binary`
- Processor: `8086`
- Bitness: `16-bit`
- Load address: `0000:0000`

자동 분석이 전부 `db`로만 표시되면 진입점을 수동으로 지정한다.

```text
G 17CC
C
P
```

진입점은 게임마다 다르다. unpack 결과 또는 DOSBox-X에서 확인한 `CS:EIP`를 사용한다.

### DOSBox-X

DOSBox-X는 실제 실행 중인 세그먼트, 스크립트·리소스 버퍼, 파일 로더를 확인하는 데 사용한다.

권장 역할 분담:

```text
disasm_mz16.py  실제 16비트 명령과 offset 확인
Cutter           함수 그래프·분기·호출 관계 확인
IDA64            함수·주석·데이터 구조 정밀 분석
DOSBox-X         실제 메모리와 제어코드 동작 검증
```

## Python 환경

IDA 7.7 전용 Python 환경과 기존 Python 환경을 분리한다.

```text
base 환경       Python 3.12 유지
ida310 환경     Python 3.10, IDA 전용
Cutter          Rizin 분석용으로 별도 사용
```

```powershell
conda create -n ida310 python=3.10 -y
```

IDA에 Python 경로를 등록할 때는 IDA를 종료하고 관리자 권한 PowerShell에서 `idapyswitch.exe`를 실행한다. 64비트 Python을 사용하는 경우 `ida64.exe` 또는 `idat64.exe`를 사용한다.

```powershell
$idaExe = Get-ChildItem -LiteralPath "C:\Program Files (x86)" -Directory -Filter "Hex-Rays IDA*" |
  ForEach-Object { Join-Path $_.FullName "idapyswitch.exe" } |
  Where-Object { Test-Path $_ } |
  Select-Object -First 1

& $idaExe --auto-apply
```

선택 화면에서는 `0`을 입력한다. `Program Files (x86)` 내부의 `sip.pyd`를 갱신하므로 관리자 권한이 필요할 수 있다.

headless 실행에서 DLL을 찾지 못하면:

```powershell
$env:PYTHONHOME = "C:\Users\<user>\miniconda3\envs\ida310"
$env:PYTHONPATH = "C:\Users\<user>\miniconda3\envs\ida310\Lib;C:\Users\<user>\miniconda3\envs\ida310\DLLs"
$env:PATH = "C:\Users\<user>\miniconda3\envs\ida310;C:\Users\<user>\miniconda3\envs\ida310\Library\bin;" + $env:PATH
```

## DOSBox-X 디버거 명령

```text
RUN                         실행 재개
C <seg> <off>               코드 뷰 이동
D <seg> <off>               데이터 뷰 이동
BP <seg> <off>              실모드 브레이크포인트
BPLIST                      브레이크포인트 목록
BPDEL <번호>                브레이크포인트 삭제
BPINT 21 3D                 DOS 파일 열기 호출 중단
BPINT 21 3F                 DOS 파일 읽기 호출 중단
F10                         한 명령 실행
LOGC <hex count>            CS:IP 중심 CPU 로그 생성
MEMDUMPBIN <seg> <off> <count> 메모리 덤프 생성
```

`U` 명령이 지원되지 않는 경우 코드 뷰 이동에는 `C`를 사용한다. 디버거 진입 단축키는 보통 `Alt+Pause`다.

## 스크립트·리소스 파일 추적

1. 재현 가능한 세이브를 준비한다.
2. DOSBox-X 디버거를 실행한다.
3. 파일 열기 호출에 중단점을 설정한다.

```text
BPINT 21 3D
RUN
```

4. 세이브를 로드하면서 `D DS DX`로 파일명을 확인한다.
5. 그래픽·음성 등 관련 없는 파일은 넘기고 대상 스크립트·리소스 파일이 열릴 때까지 `RUN`을 반복한다.
6. 파일 읽기 직후 버퍼를 확인한다.

파일이 열렸다고 해서 버퍼가 바로 평문 텍스트인 것은 아니다. 인덱스, 리소스 경로, 압축 데이터, 게임 전용 바이너리 구조가 함께 들어 있을 수 있다.

## 인터럽트와 스택 분석 주의사항

화면이 idle 상태일 때 디버거를 열면 타이머 인터럽트나 하드웨어 I/O 루틴에 걸릴 수 있다.

- `CS:EIP`가 대사 코드인지 먼저 확인한다.
- `BP`는 스택 프레임이 아니라 작업 구조체 포인터일 수 있다.
- `D SS BP`만으로 복귀 주소를 추정하지 않는다.
- `IRET` 직전에는 실제 `SS:SP`와 인터럽트 프레임 구조를 확인한다.
- 타이머 인터럽트 루틴에는 브레이크포인트를 걸지 않는다.

화면 표시 순간을 직접 잡기 어렵다면:

```text
LOGC 100000
```

을 사용해 `LOGCPU.TXT`에서 `CS:IP` 흐름을 확인한다.

## 게임별 추가 정보 기록

게임마다 다음 정보를 별도로 기록한다.

- 압축 또는 unpack 방식과 최종 분석 이미지
- 실행 이미지와 오버레이의 로드 주소
- 스크립트·리소스 파일의 확장자와 파일 열기 순서
- 텍스트 버퍼의 위치와 문자 인코딩
- 제어코드 후보와 실제 화면 출력 루틴의 연결 관계
- DOSBox-X에서 재현 가능한 세이브와 브레이크포인트

## 분석 순서 요약

```text
압축 해제
  → disasm_mz16.py로 진입점과 의심 주소 확인
  → Cutter에서 함수 그래프 분석
  → IDA64에서 함수·주석 정리
  → DOSBox-X에서 실제 스크립트·리소스 버퍼와 실행 주소 검증
  → 제어코드 의미를 확정한 뒤 인코더에 반영
```

정적 분석에서 특정 바이트 값이 발견되더라도 즉시 텍스트 제어코드라고 단정하지 않는다. BIOS, 입력, 그래픽, 설정 파서에서도 같은 값이 나타날 수 있으므로 실제 텍스트 또는 리소스 버퍼를 읽는 문맥인지 확인해야 한다.