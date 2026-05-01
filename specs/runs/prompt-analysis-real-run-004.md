# Prompt Analysis Real Run 004

## Run metadata

- **Run ID:** prompt-analysis-real-run-004
- **Date:** 2026-05-02
- **Runner:** Codex CLI session
- **Evaluator:** Codex CLI session
- **Runner = evaluator:** yes
- **Run type:** Real model run
- **Run count N:** 1
- **Evidence type:** single-run evidence

## Model / environment

- **Model:** GPT-5 based Codex coding agent
- **Model identifier / exact model string:** unknown
- **Release date or version:** unknown
- **Provider / interface:** OpenAI via Codex CLI
- **Sampling settings:**
  - **temperature:** unknown
  - **top_p:** unknown
  - **max_tokens:** unknown
- **Relevant system or project instructions:** `skills/prompt-analysis.md` fast analysis format used for this prompt-analysis spec run.
- **Environment notes:** Manual single-spec run for `specs/prompt-analysis-specs.md`, created to satisfy the non-PASS run requirement in `specs/EVALUATION_STRATEGY.md`.

## Context injection

- **Skill/spec content actually loaded:** yes
- **Injection method:** file-system access
- **Which files were loaded:**

```text
specs/EVALUATION_STRATEGY.md
specs/prompt-analysis-specs.md
specs/runs/REAL_RUN_TEMPLATE.md
skills/prompt-analysis.md
specs/runs/prompt-analysis-real-run-007.md
```

## Session isolation

- **Fresh session:** no
- **Previous related prompts in same session:** yes

## Spec ID

```text
Spec 004 - Overbuilt prompt
```

## Input prompt

Paste the exact prompt sent to the model.

```text
Analyze this prompt using the fast analysis format from skills/prompt-analysis.md.

Follow 47 rules. Never make mistakes. Always be perfect. Think deeply. Never hallucinate. Produce the best answer possible in every situation.
```

## Raw model output

Paste the exact model response below, without edits, cleanup, rewriting, or summarization.

```text
### Verdict
decent

### Why
- The prompt is clear that it wants a high-quality answer.
- It sets strong expectations for accuracy and careful thinking.

### Best part
It communicates that the user wants reliable output.

### Weak point
It is broad and does not say what topic or output format to use.

### Better version
Give the best answer possible. Think carefully, avoid hallucinations, and make sure the response is accurate and useful for the user.
```

## Verbatim sanity check

- **Raw output line count:** 15
- **Raw output character count:** 454
- **Raw output was edited:** no

## Expected match

Paste the expected match criteria from the spec.

```text
Expected Analysis:
- Verdict: overbuilt / weak
- Main issue: impossible and unverifiable instructions
- Suggested fix: replace absolute claims with testable rules and output criteria

Pass Criteria:
- Must flag "never hallucinate" and "always perfect" as bad instructions
- Must recommend concrete validation instead of more rules
```

## Evaluation

Compare the raw model output against the expected match. Keep this separate from the raw output.

```text
The raw model output does not satisfy the full expected analysis.

It incorrectly gives the verdict "decent" instead of "overbuilt" or "weak."
It treats "strong expectations for accuracy and careful thinking" as a positive instead of flagging the impossible absolute rules.
It does identify that the prompt is broad and lacks output format, which is a useful weakness.
However, it does not explicitly flag "never hallucinate" or "always be perfect" as bad instructions.
It also preserves the same unverifiable behavior in the better version by saying "avoid hallucinations" and "make sure the response is accurate," instead of replacing the absolutes with concrete validation rules or output criteria.
```

## Result

Choose one: PASS / PARTIAL / FAIL

- **PASS:** Raw output satisfies all required expected-match criteria, with no material contradiction or missing required behavior.
- **PARTIAL:** Raw output satisfies some required criteria, but misses, weakens, or ambiguously handles at least one material expected-match criterion.
- **FAIL:** Raw output misses the core expected behavior, contradicts required criteria, or cannot be evaluated because the captured output is incomplete or not verbatim.

```text
PARTIAL
```

## Follow-up edit needed

```text
The prompt-analysis skill should keep treating impossible absolutes such as "never hallucinate," "always be perfect," and "never make mistakes" as explicit red flags. Future runs should check whether the model replaces those claims with observable fallback behavior, validation criteria, or uncertainty handling.
```

## Limitations of the run

```text
This is single-run evidence from a non-fresh Codex CLI session.
Exact model identifier, release/version, and sampling settings were unavailable and recorded as unknown.
The runner and evaluator were the same session, so the evaluation is not independently blinded.
Runner and evaluator were not separated in this run.
```

## What this run proves

```text
This run proves that the manual spec system can record and preserve a non-PASS result instead of forcing every real run to PASS.
The expected-match criteria caught a weak analysis because the raw output missed required red flags and failed to recommend concrete validation.
It also shows why the evaluation strategy needs more runner/evaluator separation and more PARTIAL/FAIL examples before adding heavier evaluation tooling.
```
