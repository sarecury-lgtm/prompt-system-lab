# PSOS prompt comparison web

로컬 비교 화면은 세 가지 실행 방식을 제공한다.

## Codex 전체 실행

일반 문제 해결용 기존 PSOS다. 라우팅, 검색, 분석, 파일 읽기와 승인된 파일 변경까지 수행한다.

## 통합 AI 1회

프롬프트 제작 전용 축약 방식이다.

1. 사용자가 자연어 요청을 한 번 입력한다.
2. Codex를 정확히 한 번 호출해 Goal Ledger와 Prompt Build Brief를 함께 만든다.
3. 서버가 두 구조의 필드, 고정 조건, 완료 조건 일치를 검증한다.
4. 기존 결정론적 렌더러가 모델 호출 없이 최종 프롬프트를 조립한다.

논리적으로 필요한 Goal Ledger와 Brief 단계는 유지하지만, 사용자의 복사·붙여넣기와 모델 왕복을 줄인다. 한 호출에서 두 단계를 함께 설계하므로 수동 PSOS와 결과가 같다고 가정하지 않으며 실제 비교 대상으로 사용한다.

## 수동 PSOS 4단계

예전에 사용하던 방식이다.

1. 원래 요청으로 라우터 지시문을 복사한다.
2. Goal Ledger 결과를 붙이고 Brief 컴파일러 지시문을 복사한다.
3. Prompt Build Brief 결과를 붙이고 최종 실행기 지시문을 복사한다.
4. 최종 프롬프트를 붙인다.

수동 진행 상태는 브라우저에 보존된다.

## 비교용 복사

통합 AI 1회 결과와 수동 PSOS 최종 결과가 모두 준비되면 `두 결과 같이 복사`를 누른다. 클립보드에는 다음 형식으로 들어간다.

```text
# 통합 AI 1회 결과
...

---

# 수동 PSOS 4단계 결과
...
```

이를 ChatGPT에 붙여 도메인 절차, 고정 조건, 예외 처리, 출력 계약의 실질적인 차이를 비교한다.

## 실행

기존 서버가 열려 있다면 먼저 `Ctrl+C`로 종료한다.

```powershell
cd C:\Users\jeong\prompt-system-lab
git switch main
git pull
python -B .\scripts\problem_solving_compare_web.py --open-browser chrome
```

또는 저장소 루트에서 `start-psos-compare.cmd`를 실행한다. 서버는 기본적으로 `http://127.0.0.1:8765/`에만 열린다.
