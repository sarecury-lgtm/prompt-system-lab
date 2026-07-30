# PSOS Core Quality Improvement Plan

## 목적

PSOS의 다음 개선 목표는 기능 수를 늘리는 것이 아니라, 어떤 요청에서도 다음 세 가지를 안정적으로 만족시키는 것이다.

1. 사용자가 실제로 원한 결과를 만든다.
2. 핵심 결론을 사용자가 직접 검토할 수 있는 근거와 연결한다.
3. 특정 사례를 고치다가 코어가 해당 사례에 과적합되지 않게 한다.

수동 ChatGPT 브리지는 Codex 사용량 부족 시 사용하는 fallback이다. 이 문서는 수동 흐름 자체를 확장하는 계획이 아니라, 그 과정에서 발견된 품질 문제를 메인 PSOS에 일반화하는 계획이다.

## 중심 구조

```text
사용자 요청
  → Goal Ledger
  → Route 선택
  → 요청별 Result Contract 생성
  → Executor 실행
  → 구조·현실 receipt 검증
  → Result Contract 검증
  → 부족한 항목만 1회 repair
  → 결과 + 검토 가능한 Evidence Bundle
  → 사용자 피드백과 수정
```

`Result Contract`는 경로를 하나 더 만드는 것이 아니다. 선택된 경로가 실제 사용자 결과로 인정받기 위해 반드시 만족해야 하는 항목을 구조화한 실행 계약이다.

## Phase A — 계약 생성과 실행 전달

완료된 항목:

- Result Contract v1 JSON schema와 Python dataclass/validator
- route와 Goal Ledger에서 안전한 최소 계약 생성
- 별도 contract 모델이 사용자 요청별 세부 완료 조건을 자동 구성
- 고정 조건과 완료 조건을 바꾼 계약 거부
- contract 모델 1차 실패 시 2차 재시도, 둘 다 실패하면 최소 계약 fallback
- `result_contract.json` 원자적 저장
- executor prompt에 계약 전달
- 계약 경로·SHA-256·생성 trace를 run 기록에 저장
- 단순 DIRECT는 계약과 추가 모델 호출 생략

계약은 다음 검증 방식을 지원한다.

- `text`
- `evidence`
- `url`
- `artifact`
- `receipt`
- `visual`

상품, 복숭아, 댓글 같은 고유 단어는 코어 validator에 하드코딩하지 않는다. 사례별 필수 항목은 선언적 required output으로 표현한다.

## Phase B — 계약 검증과 focused repair

완료된 항목:

- 별도 assessment schema와 계약 검증 모델 단계
- 결과 본문, URL, evidence, artifact, receipt, visual reference의 기계 관찰
- 모델이 충족이라고 주장해도 실제 URL·artifact·receipt·시각 근거가 없으면 missing으로 덮어쓰는 하드게이트
- 최소 출처 수와 결론-출처 연결 검사
- 검증 모델 1차 실패 시 2차 재시도
- 검증 모델이 모두 실패하면 의미상 충족을 가정하지 않는 보수적 deterministic fallback
- 비파괴 경로에서만 최대 1회 focused repair
- repair 결과 재검증
- 최초 execution과 assessment를 run evidence로 보존
- repair 후에도 부족하면 `completed` 해제

실패 정책:

- `partial`: 기존 결과를 남기되 미충족 조건을 명시하고 partial로 강등
- `blocked`: 필수 artifact·receipt·capability가 없으면 blocked_by_capability로 강등
- `no_winner`: 근거 없는 우승자나 추천을 제거하고 확정 불가 결과로 교체

CODE·PROJECT 또는 이를 포함한 HYBRID는 중복 파일 변경 위험 때문에 자동 repair하지 않는다. 계약 검증과 상태 강등만 수행한다.

## 현재 파일

- `schemas/problem-solving-os-result-contract.schema.json`
- `schemas/problem-solving-os-result-contract-assessment.schema.json`
- `scripts/problem_solving_contract.py`
- `scripts/problem_solving_contract_enforcement.py`
- `scripts/problem_solving_os_contract_runtime.py`
- `tests/fixtures/result-contract-cases.json`
- `tests/test_problem_solving_contract.py`
- `tests/test_problem_solving_contract_enforcement.py`
- `tests/test_problem_solving_os_contract_runtime.py`

## 대표 회귀 사례

1. 현재 판매 상품 추천: 직접 링크·현재 상태·조건별 근거
2. 일반 최신 정보 조사: 공식 출처와 결론 대응
3. 간단 DIRECT 설명: 불필요한 계약 생략
4. 기존 프롬프트 수정: 피드백이 실제 전체본에 반영
5. 새 프롬프트 제작: 재사용 가능한 최종 지시문
6. 기존 로컬 자산 REUSE: 정확한 경로와 fingerprint
7. 작은 파일 CODE 변경: 승인 범위·receipt·검증
8. 시각 근거 판단: 원본 위치와 사용자 직접 검토
9. capability 부족: 성공을 꾸미지 않고 handoff
10. 조건이 애매한 선택: no-winner 허용

평가 기준은 임의 총점 대신 목표 보존, 경로 과잉 여부, 실제 결과 생성, 필수 출력 충족, 근거와 결론 연결, 사용자 직접 검토 가능성, 피드백 반영, 다른 사례 회귀 여부로 기록한다.

## 다음 단계 — Evidence Bundle

- evidence role과 subject 연결
- 결과 옆에 근거와 원문을 함께 표시
- 사용자의 `유지`, `의심`, `제외` 판정 저장
- 이미지 원본 위치와 대상 연결
- AI 시각 관찰과 사용자 판정을 분리해 revision에 전달

사진은 복숭아 전용 기능이 아니라 범용 `visual evidence`로 취급한다.

## 현재 경계

품질층은 아직 `scripts/problem_solving_os_contract_runtime.py`라는 얇은 통합 어댑터에 있다. canonical `problem_solving_os.py`의 backup·receipt·rollback·정책 생명주기는 변경하지 않았다. 계약 생성·검증·repair 흐름이 안정화된 뒤 이 연결부를 canonical runtime으로 흡수한다.
