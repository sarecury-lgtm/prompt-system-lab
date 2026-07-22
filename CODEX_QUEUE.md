# Codex Queue

> 목적: 채팅 연구가 끝난 뒤에만 실행할 구현 작업을 변경 범위와 검증 조건이 고정된 패킷으로 전달한다.

## 상태 규칙

- `research-required`: 선행 연구 계약이 미완료이므로 실행 금지
- `ready`: 연구 결과와 변경 승인이 모두 고정되어 실행 가능
- `complete`: 구현·검증·결과 전달 완료

현재 `ready`인 작업은 **없다**. 기존 라우터, 패턴, active 허용 목록은 동결 상태다.

## CX-ENC-001

- status: `research-required`
- 목적: Entity-Normalized Comparison 최종 계약을 저장소의 실행 가능한 선택 모듈과 결정적 검증으로 구현한다.
- 선행 연구 결과: `RQ-ENC-001`의 최종 계약이 필요하다. 현재는 18개 채택 자료와 `ENC-A001`–`ENC-A024` 행동 장부까지만 확정됨.
- 읽을 파일:
  - `CHAT_CONTEXT_PACK.md`
  - `RESEARCH_QUEUE.md`
  - `reports/entity-normalized-comparison-source-collection/action-ledger.json`
  - `reports/entity-normalized-comparison-source-collection/product-seller-supplement-action-ledger.json`
  - `reports/entity-normalized-comparison-source-collection/PRODUCT_SELLER_SUPPLEMENT.md`
- 수정 가능한 파일: 연구 계약에서 명시할 신규 `specs/`, 신규 `skills/`, 신규 targeted `tests/` 파일만. 기존 파일 수정은 별도 승인 필요.
- 수정 금지 파일:
  - `scripts/prompt_mode_compare.py`
  - `prompt-corpus/PATTERN_LESSONS_INDEX.md`
  - `specs/experiments/prompt-mode-contribution/active-source-policies.json`
  - 기존 Entity action ledger와 candidate review
  - 기존 실험 보고서
- 구현 요구사항: relation level, authority, temporal scope, 판단 불가, false merge 금지, 어댑터 경계와 live lookup 필요 여부를 계약대로 보존한다.
- 완료 조건: 고정 계약의 모든 상태가 machine-readable하고, 근거 없는 자동 통합이 차단되며, 신규 targeted 테스트가 통과함.
- 실행할 테스트: 연구 계약에 지정된 schema/판정/negative-case targeted 테스트만 실행.
- 결과 요약 저장 위치: `RESULT_INBOX/`에 `CX-ENC-001-RESULT.md` 형식으로 저장.

## CX-DG-001

- status: `research-required`
- 목적: Decision Gate를 기존 패턴과 겹치지 않는 reusable pattern으로 구현한다.
- 선행 연구 결과: `RQ-DG-001`의 자료 수집 명세와 패턴 계약, 기존 Evaluation Rubric과의 비중복 판정이 필요함.
- 읽을 파일:
  - `CHAT_CONTEXT_PACK.md`
  - `RESEARCH_QUEUE.md`
  - `prompt-corpus/PATTERN_LESSONS_INDEX.md`
  - `skills/prompt-design-workflow.md`
- 수정 가능한 파일: 명시적 동결 해제 후 `prompt-corpus/PATTERN_LESSONS_INDEX.md`, `skills/prompt-design-workflow.md`, 신규 `specs/`와 targeted `tests/`.
- 수정 금지 파일: corpus 원자료, active 허용 정책, core router, expert-collaboration 사례·평가 키, 기존 실험 보고서.
- 구현 요구사항: 선택·보류·중단·확대·전환 기준을 관찰 가능한 산출물로 만들고 사용자 가치 판단을 대신 확정하지 않는다.
- 완료 조건: 계약의 적용/금지 조건과 positive/negative 사례가 테스트되며 기존 9개 패턴 행동을 손상하지 않음.
- 실행할 테스트: 신규 pattern contract 테스트와 기존 패턴 인덱스 참조 검증 중 관련 범위만 실행.
- 결과 요약 저장 위치: `RESULT_INBOX/`에 `CX-DG-001-RESULT.md` 형식으로 저장.

## CX-AC-001

- status: `research-required`
- 목적: 복합 요청의 필수 산출물 누락을 막는 Artifact Closure 패턴을 구현한다.
- 선행 연구 결과: `RQ-AC-001`의 closure 계약과 `artifact_miss`/치명적 실패 경계가 필요함.
- 읽을 파일:
  - `CHAT_CONTEXT_PACK.md`
  - `RESEARCH_QUEUE.md`
  - `prompt-corpus/PATTERN_LESSONS_INDEX.md`
  - `skills/prompt-design-workflow.md`
  - `reports/expert-collaboration-main/main-20260714T121628Z/summary.json`
- 수정 가능한 파일: 명시적 동결 해제 후 패턴 인덱스·workflow의 해당 부분, 신규 `specs/`와 targeted `tests/`.
- 수정 금지 파일: 기존 실험 출력·점수·사례·평가 기준, active 정책, core router, corpus 원자료.
- 구현 요구사항: 요구 산출물 inventory, 완료·미완료·해당 없음·보류 상태, 최종 closure 확인을 구현하되 단순 장문 체크리스트를 강제하지 않는다.
- 완료 조건: 필수 산출물 누락을 탐지하고 정당한 보류를 실패로 오인하지 않는 targeted 테스트가 통과함.
- 실행할 테스트: 신규 artifact-closure positive/negative/conditional targeted 테스트.
- 결과 요약 저장 위치: `RESULT_INBOX/`에 `CX-AC-001-RESULT.md` 형식으로 저장.

## CX-CEG-001

- status: `research-required`
- 목적: Claim–Evidence Graph 연구 결과를 재현 가능한 action ledger와 선택 모듈 계약으로 구현한다.
- 선행 연구 결과: `RQ-CEG-001`의 자료 범위, 채택 기준, 원자 행동과 출력 계약이 필요함.
- 읽을 파일:
  - `CHAT_CONTEXT_PACK.md`
  - `RESEARCH_QUEUE.md`
  - `prompt-corpus/PATTERN_LESSONS_INDEX.md`
  - `prompt-corpus/PATTERN_VERIFICATION.md`
- 수정 가능한 파일: 연구 계약이 지정할 신규 `reports/`, `specs/`, `skills/`, targeted `tests/` 파일만.
- 수정 금지 파일: 현재 9개 패턴, core router, active 정책, corpus 원자료, 기존 실험 보고서.
- 구현 요구사항: 주장·근거·반박·모순·불확실성·출처 위치를 분리하고 간접 근거로 직접 확정하지 않는다.
- 완료 조건: 스키마, 참조 무결성, 모순 보존, 판단 불가 negative case가 모두 통과함.
- 실행할 테스트: 신규 ledger schema, dangling reference, contradiction preservation targeted 테스트.
- 결과 요약 저장 위치: `RESULT_INBOX/`에 `CX-CEG-001-RESULT.md` 형식으로 저장.

## CX-ISR-001

- status: `research-required`
- 목적: Information Sufficiency Router 계약을 기존 baseline-first 앞·뒤의 질문/조건부 진행 결정에 구현한다.
- 선행 연구 결과: `RQ-ISR-001`의 결정표, 질문 제한, 외부 조사·보류 경계와 회귀 사례가 필요함.
- 읽을 파일:
  - `CHAT_CONTEXT_PACK.md`
  - `RESEARCH_QUEUE.md`
  - `scripts/prompt_mode_compare.py`
  - `tests/test_prompt_mode_compare.py`
  - `tests/test_answer_router_smoke.py`
- 수정 가능한 파일: 명시적 동결 해제 후 `scripts/prompt_mode_compare.py`와 해당 targeted `tests/`; 계약이 요구하는 신규 schema 파일.
- 수정 금지 파일: active 7개 정책, full 자동 검색 설정, 패턴 인덱스, corpus, expert-collaboration 사례·평가 키·기존 결과.
- 구현 요구사항: 질문, 조건부 진행, 외부 조사, 보류를 결정하고 최대 질문 수와 알 수 없음 처리를 일관되게 적용한다.
- 완료 조건: 기존 baseline/pattern/active 선택을 불필요하게 바꾸지 않고, 상태 격리와 비공개 정보 차단을 포함한 회귀 테스트가 통과함.
- 실행할 테스트: router unit test와 answer-router smoke test 중 영향 범위만 실행.
- 결과 요약 저장 위치: `RESULT_INBOX/`에 `CX-ISR-001-RESULT.md` 형식으로 저장.
