# Adaptive Shopping Experiment

이 실험은 범용 AI 단계를 늘리는 대신, 온라인 상품 구매 요청에 필요한 현실 데이터를 일정 형식으로 수집하고 결정론적으로 검증하는 최소 적응형 컨트롤러다.

## 목적

기존 dynamic-loop 실험에서 확인된 다음 실패를 직접 막는다.

- 관련 대화 요약 중 강한 불호·기존 경험 누락
- 상품 데이터 대신 시장 설명과 추천문 생성
- 상품가·중량·배송비·판매 상태가 없는 후보 조기 압축
- 냉장·냉동 등 요청 범위 누락
- 미완료 결과를 최종 추천처럼 표시
- 같은 조사 방법을 반복하며 토큰만 늘리는 현상

## 실행 순서

```text
관련 대화 원문
→ 원문 인용이 붙은 context evidence
→ structured product collection
→ 결정론적 가격 계산·판매 상태·중복·조건 검사
→ 결손이 있으면 targeted gap fill 한 번
→ 검증 통과 상품만 decision model에 전달
→ 결정론적 결과 렌더링
```

AI 단계는 세 종류만 사용한다.

1. 관련 맥락에서 행동을 바꾸는 사실 추출
2. 실제 상품 옵션 데이터 수집
3. 검증 통과 상품의 최종 순위 결정

중간 추천문 작성 AI와 별도 장문 검증 AI는 사용하지 않는다.

## 핵심 안전 조건

- context fact의 `source_quote`는 제공된 맥락 원문에 실제로 존재해야 한다.
- 강한 불호·기존 사용 경험 문장은 모델이 누락해도 보수적으로 다시 보존한다.
- `available` 상품은 가격·중량·판매 상태 직접 근거가 모두 있어야 한다.
- 총결제액과 100g당 가격은 모델 값이 아니라 Python이 계산한다.
- 품절·판매 확인 불가·구매량 제한 초과·기존 불호 일치 상품은 추천 대상에서 제거한다.
- 최소 후보 수, 판매처 범위와 요청된 냉장·냉동 범위를 통과하지 못하면 한 번만 수집 방식을 바꾼다.
- 두 번째 수집 후에도 실패하면 `partial`로 저장하고 `최종 추천` 제목을 쓰지 않는다.

## 실행

```powershell
python -B scripts\problem_solving_adaptive_shopping.py `
  --request-file request.txt `
  --context-file context.txt `
  --run-id adaptive-pork-live
```

기본 결과 경로:

```text
runs/adaptive-shopping-experiments/<run-id>/
├─ request.txt
├─ context.txt
├─ context-evidence.json
├─ adaptive-shopping-state.json
└─ result.md
```

## 현재 경계

- 메인 웹 UI에는 아직 연결하지 않는다.
- 관련 대화는 현재 `--context-file`로 제공해야 하며 ChatGPT 대화 기록을 자동 탐색하지 않는다.
- 상품 페이지 접근과 검색 품질은 Codex 검색 환경에 의존한다.
- 쇼핑 외 도메인은 별도의 acquisition adapter가 필요하다.
- 실제 삼겹살 요청으로 수집 품질과 토큰 사용량을 검증한 뒤 기본 경로 승격 여부를 결정한다.
