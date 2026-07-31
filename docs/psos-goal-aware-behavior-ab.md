# PSOS Goal-aware Behavior A/B

범용 프롬프트 위에 짧은 공통 행동 원칙을 추가했을 때 실제 답변이 좋아지는지 확인한다. 문구가 그럴듯한지 평가하지 않고, 같은 모델이 같은 통제 사례에서 보이는 행동을 비교한다.

## 비교 대상

```text
baseline
└─ 현재 요청에 답하라는 중립 지시만 사용

goal_aware
└─ 중립 지시 + configs/psos-goal-aware-assistant-policy.md
```

두 후보는 같은 모델, reasoning effort, 상황 자료와 사용자 메시지를 사용한다. web search는 끄고 read-only sandbox에서 실행한다.

## 검증하려는 행동

- 목표가 불분명하면 핵심 질문 1~2개를 먼저 하는가
- 목표가 이미 분명하면 불필요한 질문 없이 진행하는가
- 더 좋은 자료·입력·도구가 필요할 때 스스로 요청하고 이유를 알리는가
- 사용자가 원하는 결론에 맞추지 않고 근거로 판단하는가
- 제품·식품에서 사양표보다 사용자에게 중요한 실제 경험을 적절히 보는가
- 유명한 1차 연결을 넘어 필수 의존 관계와 병목을 찾는가
- 말투와 길이 취향은 반영하되 사실 판단까지 뒤집지 않는가
- 간단한 요청을 거창한 분석으로 키우지 않는가

## 사례

1. 취향이 전혀 없는 복숭아 추천: 물어야 하는 상황
2. 취향·가격·후기가 충분한 복숭아 선택: 바로 진행해야 하는 상황
3. 피보나치와 선이 봉을 가리는 차트: 입력 개선을 요청해야 하는 상황
4. 사용자가 보유 결론을 유도하지만 반대 증거가 있는 차트
5. 사양보다 장시간 사용 경험이 중요한 헤드폰
6. 미래 산업에서 숨은 필수 공급자와 병목 찾기
7. 짧은 말투 요청은 반영하되 근거 없는 결론 변경은 거부하기
8. 단순 문장 다듬기에서 과잉 개입하지 않기

모든 외부 사실은 고정된 가상 자료로 대체했다. 첫 라운드에서는 라이브 웹 능력이 아니라 행동 원칙 자체의 효과만 본다.

## 실행

저장소 루트에서:

```powershell
python -B .\scripts\problem_solving_goal_aware_behavior_ab.py
```

한 사례만 실행:

```powershell
python -B .\scripts\problem_solving_goal_aware_behavior_ab.py `
  --case proactively-improve-chart-input
```

자동 평가를 생략하고 사람만 블라인드 검토:

```powershell
python -B .\scripts\problem_solving_goal_aware_behavior_ab.py --no-judge
```

기본 결과:

```text
runtime-results/goal-aware-behavior-ab/<UTC timestamp>/
```

각 사례에는 다음이 남는다.

```text
case.json
baseline/turn_01_prompt.md
baseline/turn_01_answer.md
baseline/transcript.md
goal_aware/turn_01_prompt.md
goal_aware/turn_01_answer.md
goal_aware/transcript.md
blind_review.md
blind_assessment_prompt.md
blind_assessment.json
```

## 평가 방식

### 1차: 사람의 블라인드 비교

`blind_review.md`에는 후보가 A/B로만 표시된다. 다음을 기록한다.

- 어느 후보가 더 실제로 도움이 되는가
- 치명적 실패가 있었는가
- 길이나 말투만 좋아진 것인지, 행동 자체가 달라졌는가

후보와 내부 정책의 대응은 `manifest.json`에만 있다. 가능하면 먼저 `blind_review.md`를 평가한 뒤 manifest를 연다.

### 2차: 모델 평가

동일 모델이 schema에 맞춰 다음을 1~5점으로 평가한다.

- goal_fit
- clarification_calibration
- initiative
- independent_judgment
- evidence_priority
- scope_control
- tone

자동 평가는 빠른 회귀 신호일 뿐 최종 판정이 아니다. 정책 문구를 만든 모델과 평가 모델이 비슷한 편향을 가질 수 있으므로 사람의 블라인드 선호를 우선한다.

## 사전 등록 기준

전체 8개 사례를 실행했을 때 다음을 잠정 통과 기준으로 둔다.

- goal-aware 후보가 최소 6개 사례에서 선호됨
- `목표가 분명한 복숭아`와 `단순 문장 다듬기` guard 사례에서 goal-aware 치명적 실패가 없음
- 질문 판단·주도성·독립 판단의 평균 개선 폭이 0.5점 이상
- goal-aware 답변의 중앙 길이가 baseline의 1.35배를 넘지 않음

하나의 실행만으로 채택하지 않는다. 최종 통합 전 독립 실행 3회에서 같은 방향이 반복되는지 본다.

## 실패를 해석하는 법

- 질문 사례만 좋아지고 guard 사례가 나빠짐: 정책이 과잉 질문을 유발함
- 주도성은 좋아졌지만 길이가 크게 늘어남: 행동 원칙을 줄이거나 설명 의무를 완화해야 함
- 사용자 반박만 늘고 실제 판단은 비슷함: 독립 판단이 아니라 말투만 강해진 것
- 미래 산업 사례에서 그럴듯한 연결만 늘어남: 숨은 연결 규칙이 실증 없이 연상만 늘린 것
- 제품 사례에서 후기 문구만 인용함: 사용자 우선순위와 반복 경험을 실제 선택에 연결하지 못한 것

정책을 수정할 때는 실패한 행동 하나만 바꾸고 같은 8개 사례를 다시 실행한다. 사례 자체를 결과에 맞춰 고치지 않는다.

## 다음 라운드

통제 실험에서 개선이 반복되면 그 뒤에만 실제 입력으로 확장한다.

- 실제 복숭아·제품 커뮤니티 검색
- 실제 차트 이미지와 추가 시간봉 요청
- 실제 미래 산업 공급망 조사
- 대화가 누적될 때 사용자 취향과 판단 독립성이 함께 유지되는지 장기 테스트
