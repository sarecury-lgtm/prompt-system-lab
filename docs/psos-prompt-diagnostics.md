# PSOS PROMPT Build and Diagnostics

PSOS의 PROMPT 경로에서 여러 입력을 바로 이어 붙이지 않고, 먼저 하나의 검증된 Prompt Build Brief로 정규화한 뒤 최종 프롬프트가 만들어지는 원인을 추적하는 계층이다.

## 생성 경로

```text
사용자 원문 ─┐
Goal Ledger ─┼→ Prompt Build Brief → PROMPT 실행기 입력 → 최종 프롬프트
Compiler baseline ─┘
```

## Prompt Build Brief

- 사용자 목적·고정 조건·완료 조건 보존
- 서로 다른 입력의 중복 규칙과 형식 압력 정리
- 최종 실행기에 필요한 정보만 하나의 계약으로 전달
- schema 검증과 quality runtime 통합

## 진단 범위

- 단계별 문자·줄·섹션 크기와 팽창률
- Build Brief 전후의 정보 보존과 중복 감소 trace
- 반복 규칙과 유사 문장 쌍 탐지
- 평면 Ledger, additive baseline, 중복 입력, 형식 압력 신호
- causal audit 기록
- 통제된 prompt input ablation 변형 생성
- 원래 결과를 덮어쓰지 않는 비교 실행
- 차트 프롬프트 대표 fixture 회귀

## 실행

```powershell
python -B .\scripts\problem_solving_os_quality_runtime.py --request "재사용 프롬프트를 만들어줘"
```

기존 run trace:

```powershell
python -B .\scripts\problem_solving_prompt_trace.py --run-dir .\runs\RUN_ID
```

이 계층은 프롬프트의 도메인 정답성을 자동 판정하지 않으며, 진단 결과로 원래 사용자 산출물을 수정하지 않는다.
