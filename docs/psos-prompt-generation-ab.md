# PSOS PROMPT Generation A/B

구형 PROMPT 실행기의 병렬 입력 합류와 새 Prompt Build Brief 단일 입력이 실제 결과에 미치는 영향을 같은 모델·reasoning·통제 입력으로 비교한다.

## 비교 흐름

```text
같은 사용자 요청
├─ legacy_merge: 사용자 원문 + Goal Ledger + Compiler baseline
└─ prompt_build_brief: 검증된 Prompt Build Brief 하나

각 경로에서 재사용 프롬프트 생성
→ 같은 통제 과제 입력에 적용
→ 답변을 A/B로 익명화
→ 사례별 기준과 치명적 실패로 블라인드 평가
```

## 기본 사례

- 다중 시간대 차트 매매 판단
- 댓글 분석과 자연스러운 답글
- 현재 판매 상품 조사·비교

차트와 상품 사례의 자료는 실제 시세·실제 판매 사실이 아닌 재현용 패킷이다. 첫 실험의 목적은 데이터 변동을 제거하고 프롬프트 생성 경로의 영향만 보는 것이다.

## 실행

Codex CLI가 ChatGPT 구독으로 로그인된 저장소 루트에서 실행한다.

```powershell
python -B .\scripts\problem_solving_prompt_generation_ab.py
```

한 사례만 실행:

```powershell
python -B .\scripts\problem_solving_prompt_generation_ab.py `
  --case comment-natural-reply
```

프롬프트 생성까지만 확인:

```powershell
python -B .\scripts\problem_solving_prompt_generation_ab.py `
  --generation-only `
  --no-judge
```

기본 결과 위치:

```text
runtime-results/prompt-generation-ab/<UTC timestamp>/
```

각 사례에는 다음이 남는다.

```text
case.json
compiler_baseline.json
legacy_merge/generator_prompt.md
legacy_merge/final_prompt.md
legacy_merge/application_answer.md
prompt_build_brief/generator_prompt.md
prompt_build_brief/final_prompt.md
prompt_build_brief/application_answer.md
blind_assessment_prompt.md
blind_assessment.json
```

전체 요약은 `manifest.json`과 `report.md`에 저장된다.

## 통제 조건

- 두 경로는 같은 모델과 reasoning effort를 사용한다.
- web search를 끄고 read-only sandbox만 허용한다.
- 같은 사례 입력을 두 결과에 그대로 사용한다.
- 평가자에게 `legacy_merge`와 `prompt_build_brief` 이름을 공개하지 않는다.
- 치명적 실패는 단순 점수 합보다 우선한다.
- 짧다는 이유만으로 새 경로를 선호하지 않는다.

## 해석 경계

이 실험은 다음을 확인한다.

- 목표와 고정 조건 보존
- 실제 과제 처리 정확성
- 행동 가능성
- 불확실성 조절
- 출력 형식과 반복의 비용

다음은 아직 확인하지 않는다.

- 실제 차트 이미지 판독 능력
- 라이브 판매 상태와 외부 웹 조사 정확성
- 투자 성과
- 다른 모델·다른 세션에서도 같은 우위가 반복되는지

통제 실험에서 새 경로의 우위가 확인된 뒤 실제 이미지·라이브 조사 사례를 별도 라운드로 실행한다.
