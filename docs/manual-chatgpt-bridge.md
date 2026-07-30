# PSOS Manual ChatGPT Bridge

Codex CLI를 사용할 수 없거나 포함 사용량이 부족할 때 쓰는 수동 fallback입니다. ChatGPT 웹을 비공식 API처럼 자동 조작하지 않고, 각 단계의 지시문과 응답을 사용자가 직접 옮깁니다.

## 실행

저장소 루트에서:

```powershell
python -B scripts/problem_solving_manual_web.py
```

브라우저에서 다음 주소를 엽니다.

```text
http://127.0.0.1:8766
```

서버는 loopback 주소에만 바인딩됩니다.

## 기본 흐름

1. 평소 말하듯 요청을 입력합니다.
2. 생성된 현재 단계 지시문을 먼저 복사합니다.
3. 별도 버튼으로 ChatGPT를 엽니다.
4. ChatGPT에 지시문을 보내고 완료된 응답을 브리지에 붙여넣습니다.
5. 브리지가 route 또는 execution 구조와 완료 조건을 검사합니다.
6. 다음 단계가 있으면 새 지시문을 표시하고, 끝나면 실제 결과만 보여줍니다.

복사와 ChatGPT 열기는 분리되어 있습니다. 탭이 먼저 열려 클립보드 쓰기가 실패하거나 예전 내용이 붙는 것을 막기 위한 순서입니다.

## 결과 파일

- `output.md`: 사용자가 실제로 복사하거나 사용할 결과 본문
- `result.md`: Goal Ledger, 경로, 한계가 포함된 감사용 전체 기록
- `goal_ledger.json`: 보존된 목표와 조건
- `route.json`: 경로, 실행 상태, 근거, 한계
- `manual-handoff.json`: 단계별 prompt·response·시간·SHA-256 기록

완료 화면의 **결과 전체 복사**는 `output.md`를 복사합니다.

## 조사 모드

| 모드 | 동작 |
|---|---|
| `none` | 웹 검색 capability 없이 실행합니다. 차트 분석 프롬프트처럼 외부 조사가 필요 없는 요청에 사용합니다. |
| `standard` | RESEARCH 경로에서 일반 ChatGPT 웹 검색을 사용하도록 지시합니다. |
| `deep` | RESEARCH 단계에서 심층 보고서를 먼저 받고, 별도 정규화 단계로 PSOS execution 형식에 변환합니다. |

심층 리서치는 사용자가 켰다는 이유만으로 모든 요청에 실행되지 않습니다. 라우터가 RESEARCH를 선택한 실행 단계에서만 사용합니다.

## 완료 결과 수정

완료 화면에서 **이 결과 수정**을 누르면 원본 run을 덮어쓰지 않고 child run을 만듭니다. 이전 Goal Ledger, 결과, 사용자 피드백을 수정 문맥으로 보존합니다.

## 신뢰 경계

수동 ChatGPT 세션은 로컬 저장소를 직접 읽거나 수정할 수 없습니다.

- 검증되지 않은 `created`·`modified` 파일 주장을 거부합니다.
- 완료된 REUSE는 로컬 자산을 실제로 확인할 수 없어 거부합니다.
- 브라우저 내부 검색이나 Deep research 실행은 독립 receipt로 증명할 수 없다는 한계를 기록합니다.
- 서버의 임의 최신 완료 run을 자동 복원하지 않고, 현재 브라우저가 선택한 run만 복원합니다.

## 이번 통합에서 제외한 것

Chrome DOM 자동 반환 확장, Evidence Bundle, 시각 자료 수집, Result Contract 실험은 포함하지 않습니다. 이 브리지는 명시적인 복사·붙여넣기 경계를 유지하는 최소 fallback입니다.

## 검증

```powershell
python -B -m unittest \
  tests.test_problem_solving_core_semantic_fixes \
  tests.test_manual_web_assets \
  tests.test_manual_output_copy \
  tests.test_problem_solving_manual_web \
  tests.test_problem_solving_manual_revision \
  tests.test_problem_solving_manual_deep \
  tests.test_problem_solving_manual_http \
  tests.test_chart_prompt_manual_flow
```
