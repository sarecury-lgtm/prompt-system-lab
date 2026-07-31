# PSOS deterministic prompt renderer

`problem_solving_prompt_renderer.py`는 Codex나 다른 모델 호출 없이 다음 세 입력을 합쳐 최종 프롬프트를 만든다.

1. Goal Ledger JSON
2. 검증된 Prompt Build Brief JSON
3. `configs/psos-goal-aware-assistant-policy.md`

최종 프롬프트 작성 단계에서 다시 모델을 호출하지 않으므로 같은 입력은 항상 같은 결과를 만든다. 이 렌더러는 프롬프트의 내용 품질을 새로 추론하지 않는다. Goal Ledger와 Prompt Build Brief가 이미 정한 목표·절차·고정 조건을 보존하면서 공통 판단 정책을 붙이는 역할만 한다.

## 실행

저장소 루트에서:

```powershell
python -B .\scripts\problem_solving_prompt_renderer.py `
  --ledger .\path\to\goal-ledger.json `
  --brief .\path\to\prompt-build-brief.json `
  --output .\final-prompt.md
```

정책 파일을 따로 지정할 수도 있다.

```powershell
python -B .\scripts\problem_solving_prompt_renderer.py `
  --ledger .\path\to\goal-ledger.json `
  --brief .\path\to\prompt-build-brief.json `
  --policy .\configs\psos-goal-aware-assistant-policy.md `
  --output .\final-prompt.md
```

`--output`을 생략하면 표준 출력으로 최종 프롬프트를 내보낸다.

## 검증

렌더러는 기존 `validate_prompt_build_brief`를 사용한다. 따라서 다음이 맞지 않으면 결과를 만들지 않는다.

- Brief의 `fixed_constraints`가 Goal Ledger와 문구·순서까지 동일함
- Brief의 첫 `output_contract`가 Goal Ledger의 `completion_condition`과 동일함
- 각 필드가 허용된 개수와 형식을 지킴

## 결과 구조

비어 있지 않은 항목만 다음 순서로 렌더링한다.

1. 역할과 목표
2. 공통 판단 원칙
3. 핵심 작업 절차
4. 사용할 입력·자료·도구
5. 반드시 지킬 조건
6. 기본값과 예외 처리
7. 하지 않을 일
8. 검증된 상위 맥락
9. 완료 조건과 출력
10. 실행 규칙

공통 실행 규칙은 다음 행동을 강제한다.

- 충분한 정보가 있으면 확인 질문 없이 진행
- 결과가 달라질 때만 질문 1~2개
- 선택 요청에서는 추천이나 다음 행동을 분명히 제시
- 같은 결론을 길게 다시 쓰는 것을 개선으로 취급하지 않음
- 사실·추론·불확실성을 구분

## 범위

이 렌더러는 Codex 기반 PSOS 실행기를 대체하지 않는다. 프롬프트 생성의 마지막 단계만 결정론적으로 대체한다. Goal Ledger와 Prompt Build Brief를 이 대화나 다른 도구에서 만든 뒤, 최종 프롬프트 파일을 재현 가능하게 저장할 때 사용한다.
