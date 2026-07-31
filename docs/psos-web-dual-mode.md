# PSOS web dual mode

로컬 PSOS 작업실은 두 실행 모드를 제공한다.

## Codex 전체 실행

일반 자연어 요청을 입력한다. 기존 PSOS가 Goal Ledger, 경로 선택, 모델 정책, 검색, 읽기 전용 실행 또는 승인된 파일 변경을 처리한다.

- Codex CLI 필요
- 라우팅·조사·분석·코드·파일 작업 가능
- 읽기 전용과 승인된 파일 변경 지원
- 실행 기록을 `runs/`에 보존

## Codex 없는 프롬프트 생성

사용자가 이미 정한 목표, 핵심 작업 절차, 고정 조건과 완료 조건을 입력한다. 서버는 `problem_solving_prompt_renderer.py`와 공통 goal-aware 정책을 사용해 최종 프롬프트를 결정론적으로 만든다.

- Codex와 모델 호출 없음
- 웹 검색 없음
- 파일 변경 없음
- 같은 입력은 같은 결과
- 목표나 절차를 추론해 보완하지 않음
- 결과는 일반 PSOS 실행 기록에 저장되지 않음

필수 입력은 다음 네 가지다.

1. 목표
2. 핵심 작업 절차 한 개 이상
3. 완료 조건
4. 고정 조건은 필요한 경우 입력

보조 입력·도구, 추가 출력 조건, 기본값과 예외, 제외 범위, 검증된 상위 맥락은 선택 사항이다.

## 실행

```powershell
cd C:\Users\jeong\prompt-system-lab
git switch main
git pull
python -B .\scripts\problem_solving_web.py --open-browser chrome
```

화면 상단의 `실행 엔진`에서 두 모드를 전환한다. 서버 주소는 기본적으로 `http://127.0.0.1:8765/`이며 외부 주소에는 바인딩되지 않는다.
