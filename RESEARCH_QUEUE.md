# Research Queue

> 목적: 코드와 저장소 상태를 바꾸지 않고 채팅에서 연구 명세·계약을 완성한 뒤, 구현 가능한 작업만 `CODEX_QUEUE.md`로 넘긴다.

## 운영 규칙

- 이 문서의 작업은 코드, 라우터, 패턴, corpus, 기존 실험 결과를 수정하지 않는다.
- 결과는 근거와 해석을 분리한 연구 계약 또는 자료 수집 명세로 작성한다.
- 아래의 우선순위 표시는 제안일 뿐 확정 순서가 아니다.
- Codex 전달 완료 조건을 충족하기 전에는 대응 구현 패킷을 `ready`로 바꾸지 않는다.

상태 의미:

- `chat-ready`: 현재 자료로 채팅 연구를 시작할 수 있음
- `synthesis-ready`: 자료 수집은 끝났고 계약으로 종합할 수 있음
- `blocked`: 추가 입력이나 선행 연구가 필요함

## RQ-ENC-001 — Entity-Normalized Comparison 상품 공백 종합

- 상태: `synthesis-ready`
- 제안 우선도: 근거 수집이 이미 끝나 가까운 시점에 종합하기 좋은 후보
- 연구 목적: 제품·변형·포장·판매 제안·판매자·법적 주체를 혼동하지 않는 최종 비코드 모듈 계약을 확정한다.
- 필요한 자료:
  - `reports/entity-normalized-comparison-source-collection/action-ledger.json`
  - `reports/entity-normalized-comparison-source-collection/product-seller-supplement-action-ledger.json`
  - `reports/entity-normalized-comparison-source-collection/candidate-review.json`
  - `reports/entity-normalized-comparison-source-collection/product-seller-supplement-candidate-review.json`
  - `reports/entity-normalized-comparison-source-collection/SUMMARY.md`
  - `reports/entity-normalized-comparison-source-collection/PRODUCT_SELLER_SUPPLEMENT.md`
- 채팅에서 수행할 분석: 24개 원자 행동을 공통 핵심, 상품·기업·문서 어댑터, 실시간 외부 조사로 배치하고 입력·출력·판정 불가·통합 금지·authority·temporal scope 계약을 고정한다. 남은 상품 상태 공백은 외부 조사 경계로 명시한다.
- 결과물 형식: 행동 ID와 근거 위치를 보존한 최종 모듈 계약서 1개와 positive/negative 사례 명세.
- Codex 구현 전달 완료 조건: 입력·출력 스키마, 판정 단계, 금지 규칙, fallback, 적용·금지 조건, 대상별 어댑터, 최소 검증 사례가 모두 관찰 가능한 문장으로 고정됨.

## RQ-DG-001 — Decision Gate 자료 수집 명세와 패턴 계약

- 상태: `chat-ready`
- 제안 우선도: 여러 의사결정 작업에 반복되므로 범용 패턴 후보로 검토할 가치가 있음
- 연구 목적: 대안의 선택·보류·중단·확대·전환을 수치와 증거에 연결하는 재사용 절차를 정의한다.
- 필요한 자료:
  - `CHAT_CONTEXT_PACK.md`
  - `prompt-corpus/PATTERN_LESSONS_INDEX.md`
  - `skills/prompt-design-workflow.md`
  - `reports/expert-collaboration-main/main-20260714T121628Z/summary.json`
- 채팅에서 수행할 분석: 사실 판단과 사용자 가치 판단을 분리하고, 최소 선택 기준·중단 기준·가역적 시험·재평가 시점·정보 부족 시 보류 조건을 정의한다. source 없이 가능한 공통 패턴과 전문가 자료가 필요한 선택 확장을 구분한다.
- 결과물 형식: 자료 수집 명세, pattern lesson 계약 초안, 적용/금지 예시와 판정표.
- Codex 구현 전달 완료 조건: 기존 Evaluation Rubric 및 active 자료와의 비중복 행동, 호출 신호, 오적용 방지, 관찰 가능한 출력 변화와 테스트가 고정됨.

## RQ-AC-001 — Artifact Closure 패턴 계약

- 상태: `chat-ready`
- 제안 우선도: 복합 결과물의 누락 문제를 직접 다루는 범용 후보
- 연구 목적: 요청된 산출물을 시작 전에 목록화하고 최종 답변에서 빠짐없이 닫는 절차를 정의한다.
- 필요한 자료:
  - `prompt-corpus/PATTERN_LESSONS_INDEX.md`
  - `skills/prompt-design-workflow.md`
  - `reports/expert-collaboration-main/main-20260714T121628Z/summary.json`
- 채팅에서 수행할 분석: 필수 산출물 inventory, 산출물-근거-상태 매트릭스, 미완료·해당 없음·보류 표시, 답변 전 closure check를 정의하고 단순 체크리스트 장황화와 구분한다.
- 결과물 형식: pattern lesson 계약, 산출물 closure 표준, 누락/완료/보류 positive·negative 사례.
- Codex 구현 전달 완료 조건: `artifact_miss`와 치명적 실패의 경계, 적용·금지 조건, 기존 Structured Output/Evaluation Rubric과의 차이, 테스트 가능한 통과 기준이 고정됨.

## RQ-CEG-001 — Claim–Evidence Graph 자료 수집 명세

- 상태: `chat-ready`
- 제안 우선도: 조사·논쟁·긴 문서 분석에 유망하지만 전문가 자료 수집 범위를 먼저 좁혀야 함
- 연구 목적: 주장, 근거, 반박, 출처, 불확실성의 관계를 보존하는 재사용 절차의 자료 채택 기준을 고정한다.
- 필요한 자료:
  - `prompt-corpus/PATTERN_LESSONS_INDEX.md`
  - `prompt-corpus/PATTERN_VERIFICATION.md`
  - `reports/entity-normalized-comparison-source-collection/action-ledger.json`
- 채팅에서 수행할 분석: claim/evidence/counterclaim 노드와 관계, 동일 주장 정규화, 직접·간접 근거, 모순·미해결 상태, 출처 위치 요구사항을 정의하고 Grounded Research와의 비중복 경계를 정한다.
- 결과물 형식: 자료 수집 명세, 후보 자료 유형과 채택·포화 기준, action ledger 스키마 초안.
- Codex 구현 전달 완료 조건: 수집 상한, 권위 기준, 추출할 원자 행동, 근거 위치 규칙, 자동 확정 금지 조건, 예상 출력 계약이 고정됨.

## RQ-ISR-001 — Information Sufficiency Router 설계

- 상태: `chat-ready`
- 제안 우선도: 질문 남발과 근거 없는 진행을 함께 줄일 수 있으나 core router 변경 전에 계약 검증이 필요함
- 연구 목적: 질문, 조건부 진행, 외부 조사, 보류 중 무엇을 선택할지 결정하는 범용 라우팅 계약을 만든다.
- 필요한 자료:
  - `scripts/prompt_mode_compare.py`
  - `specs/experiments/expert-collaboration/`
  - `reports/expert-collaboration-main/main-20260714T121628Z/summary.json`
  - `tests/test_answer_router_smoke.py`
- 채팅에서 수행할 분석: 필수 정보와 선호 정보, 답이 결과를 바꾸는 질문, 질문 비용, 최대 질문 수, 조건부 가정 표시, 알 수 없음, 외부 조사 필요를 분리하고 결정표를 만든다.
- 결과물 형식: router decision contract, 입력 신호·출력 상태, 질문/조건부 진행/보류 사례 세트.
- Codex 구현 전달 완료 조건: 각 경로의 필요충분 신호, 질문 제한, 비공개 정보 경계, fallback, 기존 baseline-first와의 결합점, 회귀 테스트가 고정됨.

## 제안된 진행 묶음

확정 우선순위는 아니다.

- 근거가 이미 준비된 종합 작업: `RQ-ENC-001`
- 범용 패턴 계약 후보: `RQ-DG-001`, `RQ-AC-001`
- 후속 자료 수집 명세 후보: `RQ-CEG-001`
- core router 계약 후보: `RQ-ISR-001`
