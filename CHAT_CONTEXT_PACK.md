# Chat Context Pack

> 기준일: 2026-07-22
> 목적: 새 채팅 세션이 세부 실행 로그를 읽지 않고도 프로젝트의 현재 판단 구조를 이해하도록 하는 압축 인수인계 문서

## 프로젝트의 현재 목적

이 저장소는 프롬프트 원자료를 모으는 데서 끝나지 않고, 원자료에서 재사용 가능한 행동을 추출하고 실제 프롬프트 제작과 실행 결과에서 그 행동의 가치를 검증하는 개인용 프롬프트 시스템이다.

현재 핵심 질문은 다음과 같다.

1. 일반 모델만으로 충분한 작업은 무엇인가?
2. 저장소의 공통 패턴이 결과 누락을 줄이는 작업은 무엇인가?
3. 검증된 개별 자료가 패턴에는 없는 고유 행동을 추가하는 작업은 무엇인가?
4. 관련 없는 자료가 오히려 판단을 흐리는 것을 어떻게 막을 것인가?

## 현재 사용자 제품 방향

일상 사용의 목표는 사용자가 평범한 말로 목적을 설명하면 AI가 저장소의 공식과 정책을 이용해 다른 AI에서 바로 쓸 프롬프트를 새로 작성하는 것이다.

- 기본 사용자 표면: `chatgpt-project/`
- AI 작성 계약: `chatgpt-project/PROMPT_COMPILER_INSTRUCTIONS.md`
- 저장소의 역할: 패턴, 정책, 검증 사례와 릴리스 상태의 원본
- ChatGPT Project의 역할: 사용자 요청 이해와 요청별 최종 프롬프트 작성
- `scripts/prompt_runtime.py`의 역할: AI 작성기가 아니라 로컬 결정적 template fallback

ChatGPT Project 사용은 Git 파일을 자동으로 변경하지 않는다. 공식 변경은 저장소에서 수정·테스트·commit·push·PR로 별도 관리한다.

## 현재 제작 흐름

현재 제작기는 다음 순서를 사용한다.

`baseline-first → pattern-only → 제한된 active → 사후 기여 검증 → fallback`

### 1. Baseline-first

저장소 자료를 넣기 전에 먼저 다음을 파악한다.

- 사용자의 실제 목적
- 사용자가 이미 제안한 해결 방법이나 전제
- 고정된 제약과 필요한 최종 산출물
- 실제 실행 환경에서 사용할 수 있는 파일·도구

입력만으로 충분한 설명·상담 작업이나, 필요한 도구가 없는 저장소 작업은 baseline을 유지한다.

### 2. Pattern-only

표, 계산, 비교, 평가 기준, 필수 항목, 출력 계약처럼 누락 위험이 큰 작업은 개별 corpus를 검색하기 전에 9개 패턴과 `skills/prompt-design-workflow.md`만 사용한다.

### 3. 제한된 active

active 검색은 사용자의 해결책이나 결론을 검토해야 하거나, 장기 위험·반대 가설·대안·중단 기준·가역적 시험이 필요한 경우에만 시도한다. 후보는 엄격한 검증을 통과한 7개 허용 자료로 제한되고, 작업 유형과 필수 요청 신호가 모두 맞아야 한다. 자동 사용 자료 수는 요청당 최대 1개다.

### 4. 사후 기여 검증과 fallback

항상 pattern-only 프롬프트를 먼저 만든 뒤 active 프롬프트와 비교한다. 자료가 새로운 핵심 제약, 판단 변수, 반례, 현실적 대안, 검증 방법, 중단·확대 기준 또는 필수 산출물 개선을 실제 프롬프트에 추가하지 못하면 active를 폐기하고 pattern-only로 돌아간다. active 후보가 없으면 ID 순서로 자료를 채우지 않는다.

## 현재 패턴 9개

| 패턴 | 현재 역할 |
|---|---|
| Role + Task Frame | 모호한 요청에 실제 역할, 목적, 제약, 산출물을 부여 |
| Interface Emulation | 실제 실행과 모의 인터페이스 출력을 분리 |
| Prompt Improvement Loop | 약한 프롬프트의 누락을 진단하고 수정·재검증 |
| Defensive Jailbreak Analysis | 공격 문구를 강화하지 않고 구조와 실패 유형만 방어적으로 분석 |
| Grounded Research | 출처 확인, 사실·추론 분리, 불확실성 표시 후 결론 |
| Structured Output / Extraction | 필드, null 정책, 증거 규칙, 정확한 출력 계약 정의 |
| Evaluation Rubric | 관찰 가능한 기준, 점수 앵커, 통과·실패 규칙 정의 |
| Persistent Project Instruction | 지속 지침의 트리거, 우선순위, 라우팅, 경계, fallback 정의 |
| Coding-Agent Workflow | 관련 파일 확인, 최소 변경, 검증, 변경 요약 |

패턴의 정확한 문구와 출처는 `prompt-corpus/PATTERN_LESSONS_INDEX.md`가 기준이다.

## Core router의 현재 기능

구현 기준 파일은 `scripts/prompt_mode_compare.py`다.

- `baseline_first_analysis`: 목적, 제안된 해법, 제약, 산출물 위험, 도구 가능 여부를 먼저 분석
- `active_policy_matches`: 요청 유형과 필수 신호가 active 자료의 좁은 적용 조건과 맞는지 검사
- `select_relevant_active_sources`: 의미 관련성 및 직접 기여 가능성을 검사하고 최소 자료만 선택
- `route_request`: baseline, pattern-only, active 중 하나를 선택하고 제외 자료·이유·fallback을 기록
- contribution dry-run: pattern-only와 active 프롬프트를 비교해 고유 기여가 없으면 pattern-only로 복귀

현재 라우터는 한국어와 영어 신호를 함께 사용한다. 단순 키워드 일치만으로 active를 확정하지 않으며, 실행 도구가 필요한 자료는 실제 도구 권한이 없으면 제외한다.

## 실전 active 허용 자료 7개

정확한 정책은 `specs/experiments/prompt-mode-contribution/active-source-policies.json`이 기준이다.

| Source | 좁은 적용 조건 | 적용 금지 요약 |
|---|---|---|
| PR002 | 메타 채널과 모의 도구 입력을 구분해야 하는 텍스트 인터페이스 시뮬레이션 | 실제 명령 실행, 단순 단일 채널 출력 |
| PR026 | 탈옥·적대적 프롬프트 사고를 비운영적으로 분류하고 회귀 시험하는 작업 | 우회 문구 복원·강화, 일반 보안 작업 |
| PR065 | 반복 가능하고 기계 실행 가능한 평가·벤치마크·회귀 실험 설계 | 답변 하나의 일회성 평가, 실행 자료 없는 조언 |
| PR086 | Cursor 저장소에서 영역별 `.cursor/rules/*.mdc` 지속 규칙 설계 | Cursor가 아닌 일반 지침, 일회성 코딩 작업 |
| PR089 | 작업 유형마다 도구·파일 권한이 다른 저장소 에이전트 운영 설계 | 단순 코딩, 권한 차이가 없는 모드 선택 |
| PR091 | 승인 파일만 처리하는 후속 자동 적용기용 정확 일치 패치 계약 | 에이전트가 직접 편집하는 일반 작업, 단순 코드 리뷰 |
| PR093 | 진입점·의존성·파일 간 계약이 중요한 다중 파일 앱 생성·완성 | 단일 파일·한 줄 수정, 파일 도구 없는 설명 |

공통 규칙:

- 의미가 비슷하다는 이유만으로 선택하지 않는다.
- 작업 유형과 필수 신호가 모두 맞아야 한다.
- 고유 행동이 최종 프롬프트에 나타나지 않으면 fallback한다.
- PR039와 연구용 6개 자료는 실전 active 후보가 아니다.

## Full 자동 검색 상태

full corpus 자동 검색은 비활성화되어 있다. 정책 파일의 `full_corpus_auto_search`는 `false`이고, 라우터의 자동 선택 모드는 `baseline`, `pattern-only`, `active`뿐이다. full은 과거 비교 실험용 조건이며 기본 제작 경로가 아니다.

## 주요 실험 결과와 확정 결론

### Prompt Improvement Loop 최소 실험

`specs/experiments/prompt-improvement-loop-minimal/RUN_RECORD_001.md`

- Stage 1: baseline 평균 7.6, candidate v1 평균 9.6, 5개 중 4승, PASS
- 수정 대상 PIL-003: v1 7점에서 v2 10점, 목표 약점 해결, 회귀 없음, PASS
- 한계: 모델·세션·평가자 식별 정보가 없고 단일 실행 증거이므로 일반화할 수 없음

### Corpus mode 3개 작업 성능 실험

`reports/corpus-mode-performance/corpus-mode-performance-20260714T0003/final-results.json`

- 27개 결과에서 baseline 19.28, full 19.44, 당시 active 19.67
- JSON 추출은 세 조건이 모두 20점으로 차이가 없었음
- 작업이 3개뿐이고 controlled input이므로 corpus 품질의 일반적 효과를 증명하지 않음

### Expert-collaboration 본 실험

`reports/expert-collaboration-main/main-20260714T121628Z/summary.json`

- 기본 64회와 추가 6회, 총 70회 실행, 입력·평가 기준 고정 유지, PASS
- 사례별 승자: A3 baseline; A7 active; C9 full; C10 pattern-only; C11 active; C13 active; C14 pattern-only; C16 active
- 전체 평균: baseline 15.333, pattern-only 14.833, active 16.157, full 15.304
- full은 active보다 평균 0.853 낮았고, 8개 중 5개 사례에서 낮았음
- 치명적 실패, 순응형 치명적 실패, 독단형 치명적 실패는 모두 0
- 확정 결론: 모든 작업에 맞는 단일 모드는 없으며, 관련 없는 corpus 주입은 성능을 낮출 수 있다.

### 보수적 active 정책 검증

`reports/prompt-mode-comparison/actual-usage-active-policy-20260716-v4/summary.json`

- 실제 사용 기록 12개에서 baseline 2, pattern-only 10, active 최종 유지 0
- active 시도 1건은 고유 기여가 없어 pattern-only로 fallback
- 7개 허용 목록, 요청당 1개 제한, full 미선택, 미사용 자료 미기여 처리가 모두 통과
- 이 결과는 라우터가 보수적으로 작동한다는 증거이지 active 자료가 가치 없다는 증거는 아니다.

## Entity-Normalized Comparison 연구 상태

위치는 `reports/entity-normalized-comparison-source-collection/`이다.

- 1차 수집: 공식 자료 후보 21개 검토, 12개 채택, 원자 행동 14개 (`ENC-A001`–`ENC-A014`)
- 상품·판매자 보충: 후보 8개 검토, 6개 채택, 원자 행동 10개 추가 (`ENC-A015`–`ENC-A024`)
- 합계: 채택 자료 18개, 원자 행동 24개
- 현재 정의 가능: 제품, 변형, 포장, offer, 판매자, 법적 주체를 별도 계층으로 보존; 판매자 SKU의 범위; 물리·가상 묶음; 리퍼비시와 재제조; 제조사·수입자·유통사·판매자 역할; 공식 판매자의 공급자 측 증거와 시점
- 남은 공백: 신품·중고 범용 등급, 재포장, 지역판, `renewed` 용어, 공급자가 공식 판매자 정보를 공개하지 않을 때의 대체 검증
- 아직 하지 않은 일: 최종 모듈 계약 작성, 코드·라우터·패턴 구현, positive-control, 성능 실험

## 동결된 항목

명시적인 해제 결정 전에는 다음을 변경하지 않는다.

- baseline-first 라우팅 원칙과 기존 직접 관련성·사후 기여 게이트
- 실전 active 허용 자료 7개와 제외 목록
- full 자동 검색 비활성화
- 현재 9개 패턴과 기존 reusable move
- expert-collaboration 8개 사례, public input, 질문표, evaluator key, 평가 기준, 치명적 실패 정의
- 기존 실험 결과와 점수
- Entity-Normalized Comparison의 기존 원자료 장부와 행동 ID; 추가 연구는 별도 보충 장부로만 기록

## 아직 변경 가능한 항목

- `RESEARCH_QUEUE.md`에 있는 코드 없는 연구 명세와 계약 초안
- 연구가 완료된 뒤 새 pattern 또는 active module로 승격할지에 대한 판단
- Entity-Normalized Comparison 최종 계약의 아직 작성되지 않은 구조
- 외부 전문자료 수집 장부의 신규 보충 파일
- `CODEX_QUEUE.md`의 패킷 상태와 승인 범위
- 인수인계 문서와 결과 inbox 운영 규칙

## 주요 파일과 보고서

| 경로 | 역할 |
|---|---|
| `README.md` | 저장소의 원래 목적과 폴더 안내 |
| `prompt-corpus/PATTERN_LESSONS_INDEX.md` | 9개 패턴의 기준 문서 |
| `skills/prompt-design-workflow.md` | 패턴 기반 프롬프트 제작 절차 |
| `scripts/prompt_mode_compare.py` | baseline-first 라우팅, active 검색·fallback 구현 |
| `specs/experiments/prompt-mode-contribution/active-source-policies.json` | 실전 active 7개 허용 목록과 좁은 조건 |
| `reports/prompt-mode-comparison/actual-usage-active-policy-20260716-v4/summary.json` | 최신 active 정책 dry-run 요약 |
| `reports/expert-collaboration-main/main-20260714T121628Z/summary.json` | 8개 사례 본 실험 요약 |
| `specs/experiments/prompt-improvement-loop-minimal/RUN_RECORD_001.md` | 닫힌 최소 개선 실험 기록 |
| `reports/entity-normalized-comparison-source-collection/action-ledger.json` | Entity 연구 1차 행동 14개 |
| `reports/entity-normalized-comparison-source-collection/product-seller-supplement-action-ledger.json` | 상품·판매자 보충 행동 10개 |
| `reports/entity-normalized-comparison-source-collection/PRODUCT_SELLER_SUPPLEMENT.md` | 상품·판매자 연구의 현재 결론 |
| `RESEARCH_QUEUE.md` | 채팅에서 진행할 코드 없는 연구 큐 |
| `CODEX_QUEUE.md` | 연구 완료 후 Codex가 수행할 변경 패킷 |
| `RESULT_INBOX/README.md` | Codex 결과 전달 규칙 |

## 새 세션에서 읽을 최소 파일

### 단순 현황 파악

1. `CHAT_CONTEXT_PACK.md`

이 한 파일만으로 목적, 현재 제작 흐름, 동결 상태, 실험 결론, 다음 연구 범위를 설명할 수 있어야 한다.

### 채팅 연구를 시작할 때

1. `CHAT_CONTEXT_PACK.md`
2. `RESEARCH_QUEUE.md`
3. 해당 항목이 가리키는 기존 근거 파일

### Codex 구현을 시작할 때

1. `CHAT_CONTEXT_PACK.md`
2. `CODEX_QUEUE.md`
3. 선택한 패킷의 `읽을 파일`

`status: ready`가 아닌 Codex 패킷은 실행하지 않는다.
