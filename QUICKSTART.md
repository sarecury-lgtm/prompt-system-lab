# Prompt Runtime v0.1 Quickstart

## 준비 사항

- Python 3.11 이상
- 저장소 루트에서 명령 실행
- 문맥 파일을 넣을 경우 UTF-8 텍스트 파일 사용

## 가장 간단한 실행 명령

```powershell
python scripts/prompt_runtime.py "요청을 여기에 입력하세요"
```

## 요청 문자열을 넣는 예시

```powershell
python scripts/prompt_runtime.py "세 가지 서비스의 가격과 위험을 표로 비교해 주세요."
```

## 파일을 같이 넣는 예시

```powershell
python scripts/prompt_runtime.py "이 문맥을 바탕으로 실행 계획을 작성해 주세요." --context .\notes.txt
```

여러 파일은 `--context`를 반복해서 넣습니다. 대상 모델이 실제 파일·명령 도구를 사용할 수 있는 요청이라면 `--tools-allowed`도 추가합니다.

## 최종 결과 위치

경로를 생략하면 다음 두 파일이 생성됩니다.

- `runtime-results/<실행시각>/prompt.txt`: 바로 사용할 최종 프롬프트
- `runtime-results/<실행시각>/routing.json`: 모드, 이유, 패턴, active source, fallback과 오류 상세

원하는 프롬프트 경로를 지정할 수도 있습니다.

```powershell
python scripts/prompt_runtime.py "회의록에서 결정 사항을 JSON으로 추출해 주세요." --output .\out\meeting-prompt.txt
```

이 경우 상세 기록은 `out/meeting-prompt.routing.json`에 저장됩니다.

## 오류가 발생했을 때 확인할 것

1. 명령을 저장소 루트에서 실행했는지 확인합니다.
2. `python --version`이 3.11 이상인지 확인합니다.
3. `--context` 파일이 존재하고 UTF-8인지 확인합니다. 문맥 파일 하나를 못 읽어도 나머지 입력으로 프롬프트는 생성됩니다.
4. 화면의 `fallback 이유`와 `routing.json`의 `errors`를 확인합니다.
5. 저장 오류가 나면 화면에 출력된 최종 프롬프트를 사용하고 출력 폴더 권한을 확인합니다.

## 입력과 화면 출력

입력은 사용자 요청 문자열, 선택적 `--context`, 선택적 `--output`입니다. 화면에는 선택 모드와 짧은 이유, 사용 패턴, active source, fallback 여부, 결과 파일 위치만 표시합니다. 프롬프트 전문은 `prompt.txt`, 상세 판단은 `routing.json`에서 확인합니다.

## 내부 동작

실행판은 `scripts/prompt_mode_compare.py`의 기존 baseline-first 라우팅과 `active-source-policies.json`을 그대로 사용합니다.

1. baseline 프롬프트를 먼저 만듭니다.
2. 라우터가 필요하다고 판단하면 기존 9개 패턴으로 pattern-only 프롬프트를 만듭니다.
3. 기존 허용 목록 7개 중 직접 관련성 게이트를 통과한 자료가 하나 있을 때만 active를 만듭니다.
4. active의 고유 행동과 필수 변화가 실제로 추가됐을 때만 active를 유지합니다.
5. active 실패는 pattern-only로, pattern-only 실패는 baseline으로 돌아갑니다.

full corpus 자동 검색은 실행하지 않으며, active source는 요청당 최대 1개입니다. 이 명령은 최종 프롬프트만 만들고 그 프롬프트가 요청하는 작업 자체는 실행하지 않습니다.

## 개발자 검증

```powershell
python -m unittest discover -s tests -v
```
