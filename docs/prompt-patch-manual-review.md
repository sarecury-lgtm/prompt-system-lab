# PROMPT baseline·patch 수동 적용 검증

이 검증은 Codex CLI나 OpenAI API를 호출하지 않는다. 이미 만든 baseline 프롬프트와 선택적인 패치 후보를 같은 통제 입력에 적용하고, 답변과 블라인드 판정만 파일로 기록한다.

## 목적

- 검증된 baseline 절차가 불필요하게 줄어드는 것을 막는다.
- 패치는 실제 누락이나 충돌을 고칠 때만 후보가 된다.
- 길이 축소나 문체 변경만으로는 승격하지 않는다.
- 동률과 무승부를 허용한다.
- 결과는 승격 권고만 만들며 runtime bundle을 자동 변경하지 않는다.

기본 사례는 다음 세 가지다.

- 다중 시간대 차트 매매 판단
- 댓글 분석과 자연스러운 답글
- 현재 판매 상품 조사·비교

## 1. 검증 팩 준비

패치 파일이 없으면 해당 사례는 baseline 유지 후보로 준비된다.

```powershell
python -B .\scripts\problem_solving_prompt_patch_review.py prepare
```

선택적인 패치 후보는 `<case-id>.md` 이름으로 넣는다.

```text
patches/
├─ chart-trade-plan.md
├─ comment-natural-reply.md
└─ product-evidence-choice.md
```

```powershell
python -B .\scripts\problem_solving_prompt_patch_review.py prepare `
  --patch-dir ".\patches"
```

생성 위치:

```text
runtime-results/prompt-patch-review/<timestamp>/
├─ manifest.json
├─ review-pack.md
└─ cases/
   └─ <case-id>/
      ├─ blind-pack.md
      ├─ prompts/
      ├─ answers/
      ├─ review.json
      └─ mapping.private.json
```

`review-pack.md`를 ChatGPT에 제공해 후보 A와 B를 각각 적용한다. 결과는 각 사례의 `answers/A.md`, `answers/B.md`에 넣고, 후보 정체를 보지 않은 상태로 `review.json`을 작성한다.

## 2. 결과 공개와 판정

```powershell
python -B .\scripts\problem_solving_prompt_patch_review.py finalize `
  --run-dir ".\runtime-results\prompt-patch-review\<timestamp>"
```

판정:

- `promote_patch`: 패치만 블라인드 선호되고 치명적 실패가 없음
- `keep_baseline`: baseline 선호 또는 패치의 치명적 실패
- `no_winner`: 동률 또는 무선호
- `baseline_retained`: 패치 후보가 baseline과 동일함

최종 결과는 `report.md`, 기계 판독 결과는 `finalized.json`에 저장된다.

## 경계

이 도구는 AI 답변을 생성하지 않는다. ChatGPT나 다른 모델이 만든 답변을 기록하고 검증하는 수동 평가 장치다. 따라서 Codex 로그인, API 키, 모델 이름, 네트워크 권한이 필요하지 않다.
