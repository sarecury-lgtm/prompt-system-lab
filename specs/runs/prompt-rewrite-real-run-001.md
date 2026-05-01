# Prompt Rewrite Real Run 001

## Run metadata

- **Run ID:** prompt-rewrite-real-run-001
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
- **Relevant system or project instructions:** `skills/prompt-rewrite.md` rewrite behavior used for this prompt-rewrite spec run.
- **Environment notes:** Manual single-spec run for `specs/prompt-rewrite-specs.md`.

## Context injection

- **Skill/spec content actually loaded:** yes
- **Injection method:** file-system access
- **Which files were loaded:**

```text
specs/runs/REAL_RUN_TEMPLATE.md
skills/prompt-rewrite.md
specs/prompt-rewrite-specs.md
specs/runs/prompt-analysis-real-run-003.md
specs/runs/prompt-analysis-real-run-007.md
```

## Session isolation

- **Fresh session:** no
- **Previous related prompts in same session:** yes

## Spec ID

```text
Spec 001 - Vague explanation prompt
```

## Input prompt

Paste the exact prompt sent to the model.

```text
Rewrite this prompt using skills/prompt-rewrite.md.

Explain this well.
```

## Raw model output

Paste the exact model response below, without edits, cleanup, rewriting, or summarization.

````text
### Improved Prompt

```text
Explain this for a beginner in 5 bullet points. Include:
1. a plain-language summary
2. the three most important ideas
3. one concrete example
4. one common misunderstanding to avoid
5. a short takeaway

Avoid jargon unless you define it. If the topic is missing, ask me to provide the text or concept first.
```

### What Changed

- Made "well" measurable with audience, length, and structure.
- Added an example and a common misunderstanding.
- Added a fallback for missing topic/context.
````

## Verbatim sanity check

- **Raw output line count:** 18
- **Raw output character count:** 519
- **Raw output was edited:** no

## Expected match

Paste the expected match criteria from the spec.

```text
Expected Rewrite:
- Adds target audience
- Adds length or structure
- Adds example/common mistake if useful

Pass Criteria:
- Must not just make it longer
- Must make "well" measurable
```

## Evaluation

Compare the raw model output against the expected match. Keep this separate from the raw output.

```text
The raw model output satisfies the expected rewrite criteria.

It adds a target audience: "for a beginner."
It adds both length and structure: "in 5 bullet points" with five named content requirements.
It adds a concrete example requirement and a common misunderstanding requirement.
It does not only make the prompt longer; it converts "well" into testable requirements for audience, structure, clarity, example, misunderstanding, and takeaway.
It also adds a practical fallback for missing topic/context.
```

## Result

Choose one: PASS / PARTIAL / FAIL

- **PASS:** Raw output satisfies all required expected-match criteria, with no material contradiction or missing required behavior.
- **PARTIAL:** Raw output satisfies some required criteria, but misses, weakens, or ambiguously handles at least one material expected-match criterion.
- **FAIL:** Raw output misses the core expected behavior, contradicts required criteria, or cannot be evaluated because the captured output is incomplete or not verbatim.

```text
PASS
```

## Follow-up edit needed

```text
None.
```

## Limitations of the run

```text
This is single-run evidence from a non-fresh Codex CLI session.
Exact model identifier, release/version, and sampling settings were unavailable and recorded as unknown.
The runner and evaluator were the same session, so the evaluation is not independently blinded.
Only Spec 001 was evaluated, so this run does not establish broader prompt-rewrite skill coverage.
```
