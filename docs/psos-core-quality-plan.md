# PSOS Core Quality Improvement Plan

## 목적

PSOS의 다음 개선 목표는 기능 수를 늘리는 것이 아니라, 어떤 요청에서도 다음 세 가지를 안정적으로 만족시키는 것이다.

1. 사용자가 실제로 원한 결과를 만든다.
2. 핵심 결론을 사용자가 직접 검토할 수 있는 근거와 연결한다.
3. 특정 사례를 고치다가 코어가 해당 사례에 과적합되지 않게 한다.

수동 ChatGPT 브리지는 Codex 사용량 부족 시 사용하는 fallback이다. 이 문서는 수동 흐름 자체를 확장하는 계획이 아니라, 그 과정에서 발견된 품질 문제를 메인 PSOS에 일반화하는 계획이다.

## 현재 상태 진단

메인 PSOS는 실행 신뢰와 안전성에는 강하다.

- Goal Ledger와 Solution Router로 목적과 경로를 기록한다.
- schema와 validator로 구조화 결과를 검사한다.
- REUSE 자산 fingerprint, CODE·PROJECT workspace receipt, backup과 rollback을 제공한다.
- 실행 기록과 정책 학습 생명주기를 분리한다.

반면 결과 유용성 검증은 상대적으로 얇다.

- `completion_condition`은 자연어 문자열이지만 실행 후 기계적으로 대조되지 않는다.
- 완료된 RESEARCH는 현재 `evidence.kind == web`인 항목이 하나 이상 있으면 기본 검사를 통과할 수 있다.
- 요청에 따라 달라지는 직접 링크, 최신 판매 상태, 원문 인용, 이미지 근거, 비교 대상 수, 실제 파일 존재 같은 조건을 공통 구조로 표현하지 못한다.
- 생성 결과가 부족할 때 빠진 항목만 보충하는 repair 단계가 없다.
- 사용자는 최종 문장과 evidence 배열을 받을 뿐, 핵심 판단 근거를 같은 화면에서 검토하고 유지·의심·제외 판정을 남기기 어렵다.

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

## 1. 요청별 Result Contract

### 공통 필드

현재 Phase A 기반 구현은 다음 파일에 있다.

- `schemas/problem-solving-os-result-contract.schema.json`
- `scripts/problem_solving_contract.py`
- `tests/fixtures/result-contract-cases.json`
- `tests/test_problem_solving_contract.py`

```json
{
  "version": 1,
  "route": "RESEARCH",
  "result_type": "research",
  "must_preserve": ["사용자의 고정 조건"],
  "required_outputs": [
    {
      "id": "stable-id",
      "description": "최종 결과에 반드시 존재해야 하는 내용",
      "verification": "text | evidence | url | artifact | receipt | visual"
    }
  ],
  "evidence_requirements": {
    "minimum_sources": 0,
    "source_roles": [],
    "claim_source_mapping": false
  },
  "user_review": {
    "needed": false,
    "evidence_types": []
  },
  "failure_policy": "partial | blocked | no_winner"
}
```

### 원칙

- 계약은 사용자 요청과 Goal Ledger에서 생성한다.
- 상품, 복숭아, 댓글 같은 고유 단어를 코어 validator에 하드코딩하지 않는다.
- 범용 계약 템플릿은 모듈로 분리한다.
- 계약을 만들 수 없는 단순 DIRECT 요청은 기존 흐름을 유지한다.
- 계약 조건을 충족하지 못하면 근거 없는 완료보다 `partial`, `blocked`, `no_winner`를 택한다.
- 사례별 필수 항목은 키워드 추론이 아니라 선언적 `required_outputs`로 전달한다.

### 예시

#### 현재 판매 상품 조사

- 개별 상품 식별 정보
- 현재 상태 확인 시각
- 직접 대상 URL
- 가격·구성·판매자
- 핵심 선호 조건별 근거
- 판매자 주장·독립 자료·후기·추론 분리

#### 재사용 프롬프트 수정

- 기존 산출물 전체본 보존
- 피드백의 교체·추가·삭제 요구 반영
- 분석 보고서가 아니라 실제 수정본 반환
- 원래 목적·출력 계약·사용자 말투 보존

#### 파일 생성·수정

- 승인된 경로
- 실제 파일 존재와 hash
- 실행 가능한 검증 결과
- 보고된 artifact와 workspace 변화 일치

#### 시각 근거가 중요한 판단

- 원본 이미지 또는 원본 페이지 위치
- 이미지가 연결된 대상 식별자
- 판매자 이미지와 사용자 이미지 구분
- AI 시각 해석과 관찰 사실 분리
- 사용자가 원본을 직접 검토할 수 있는 표시

## 2. Contract Validator와 Repair

### 검증 순서

1. 기존 JSON schema 검증
2. capability와 route 완료 조건 검증
3. receipt와 실제 파일·자산 변화 검증
4. Result Contract 검증
5. 실패 시 빠진 항목 목록 생성

### Repair 원칙

- 전체 작업을 처음부터 반복하지 않는다.
- 빠진 항목과 기존 결과를 executor에 전달해 한 번만 보충한다.
- 새 조사나 도구 사용이 필요하면 capability를 다시 확인한다.
- repair 후에도 실패하면 완료를 꾸미지 않는다.
- 최초 결과와 repair 결과를 모두 run evidence에 남긴다.

## 3. Evidence Bundle과 사용자 검토

`evidence`를 모델 내부 기록으로만 두지 않고 사용자 검토 단위로 확장한다.

### Evidence Item 초안

```json
{
  "id": "evidence-id",
  "subject_id": "후보 또는 주장 식별자",
  "kind": "web | local | command_output | provided_context | image",
  "source": "원본 위치",
  "finding": "이 근거가 직접 보여주는 것",
  "role": "fact | seller_claim | review | inference | visual_observation",
  "reviewable": true
}
```

### 사용자 화면

- 최종 결과와 핵심 근거를 같은 화면에 표시한다.
- 출처 원문과 이미지를 직접 열어볼 수 있게 한다.
- 사용자가 근거 또는 후보에 `유지`, `의심`, `제외`를 표시할 수 있게 한다.
- 사용자 판정은 기존 결과를 덮어쓰지 않고 revision 입력으로 저장한다.
- 이미지는 별도 복숭아 기능이 아니라 범용 `visual evidence`로 취급한다.

## 4. 대표 회귀 사례

다음 사례를 고정하고 코어 변경마다 모두 확인한다.

1. 현재 판매 상품 추천: 직접 링크·현재 상태·조건별 근거가 필요함
2. 일반 최신 정보 조사: 공식 출처와 결론의 대응이 필요함
3. 간단 설명 DIRECT: 불필요한 계약과 프로젝트화를 만들지 않아야 함
4. 기존 프롬프트 수정: 피드백이 실제 전체본에 반영돼야 함
5. 새 프롬프트 제작: 재사용 가능한 최종 지시문이 산출물이어야 함
6. 기존 로컬 자산 REUSE: 정확한 경로와 fingerprint가 필요함
7. 작은 파일 CODE 변경: 승인 범위·receipt·검증이 필요함
8. 시각 근거 판단: 원본 이미지와 대상 연결, 사용자 직접 검토가 필요함
9. capability 부족 요청: 성공을 꾸미지 않고 실행 가능한 handoff를 제공해야 함
10. 애매한 조건 요청: 필요한 경우 한계 또는 no-winner를 허용해야 함

평가 기준은 임의 총점 대신 다음 판정으로 기록한다.

- 목표 보존
- 경로 과잉 여부
- 실제 결과 생성
- 필수 출력 충족
- 근거와 결론 연결
- 사용자의 직접 검토 가능성
- 피드백의 실제 반영
- 다른 사례에 대한 회귀 여부

## 5. 수동 브리지에서 메인으로 가져갈 것

### 가져갈 개념

- 완료 결과를 원본 보존 revision으로 수정하는 흐름
- 같은 경로 유지가 기본이고 명시적일 때만 reroute하는 원칙
- 심층 조사 결과를 정규화하기 전에 품질을 검사하는 원칙
- 결과 정규화 과정에서 URL·근거가 유실되지 않는지 재검사하는 원칙
- 화면이 현재 사용자가 할 일 하나를 명확히 보여주는 방식

### 메인 코어에 그대로 넣지 않을 것

- 복사·붙여넣기 왕복
- 수동 ChatGPT 단계명
- Chrome 확장 프로그램
- 상품 요청을 한국어 키워드 정규식으로 감지하는 방식
- 직접 상품 URL 3개처럼 한 사례에서 나온 숫자를 모든 조사에 고정하는 방식

## 6. 구현 순서

### Phase A — 계약 기반 마련

현재 완료:

- Result Contract v1 JSON schema와 dataclass
- route 기반의 최소 기본 계약
- 사례별 조건을 선언적으로 추가하는 API
- 단순 DIRECT 계약 생략
- 기존 run 기록에서 `result_contract.json`을 미리 생성하는 CLI
- 대표 회귀 사례 10개
- focused CI

다음 연결 작업:

- 라우터가 승인된 뒤 canonical runtime에서 계약 생성
- executor prompt에 계약 전달
- run serialization에 계약 경로와 hash 기록

### Phase B — 검증과 repair

- contract validator 구현
- 빠진 항목을 구조화해 기록
- 최대 1회의 focused repair 실행
- 실패 시 partial·blocked·no-winner 처리

### Phase C — Evidence Bundle

- evidence role과 subject 연결 추가
- 웹 UI에서 근거와 원문을 결과 옆에 표시
- 사용자의 유지·의심·제외 판정 저장

### Phase D — Visual Evidence

- 이미지 원본 위치와 대상 연결 계약
- 사용자 갤러리 검토 UI
- AI 관찰과 사용자 판정을 분리해 revision에 전달

## 현재 경계

Phase A 기반 모듈은 canonical runtime과 분리되어 있다. 이는 기존 169개 테스트와 파일 변경 안전장치를 한 번에 흔들지 않고 계약 형식과 대표 사례를 먼저 고정하기 위한 의도적인 단계다. 다음 변경에서 `scripts/problem_solving_os.py`의 라우터 승인 직후에 연결한다.
