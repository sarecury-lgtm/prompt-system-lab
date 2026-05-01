# Prompt Analysis Real Run 005

## Run metadata

- **Run ID:** prompt-analysis-real-run-005
- **Date:** 2026-05-01
- **Runner:** Codex CLI session
- **Evaluator:** Codex CLI session
- **Runner = evaluator:** yes
- **Run type:** Real model run
- **Run count N:** 1
- **Evidence type:** single-run evidence

## Model / environment

- **Model:** GPT-5 based Codex coding agent
- **Model identifier / exact model string:** Not exposed by the Codex CLI session; system identity is Codex, a coding agent based on GPT-5.
- **Release date or version:** Not exposed by the Codex CLI session.
- **Provider / interface:** OpenAI via Codex CLI
- **Sampling settings:**
  - **temperature:** Not exposed; default session setting.
  - **top_p:** Not exposed; default session setting.
  - **max_tokens:** Not exposed; default session setting.
- **Relevant system or project instructions:** `skills/prompt-analysis.md` fast analysis format used for this prompt-analysis spec run.
- **Environment notes:** Manual single-spec run for `specs/prompt-analysis-specs.md`.

## Context injection

- **Skill/spec content actually loaded:** yes
- **Injection method:** file-system access
- **Which files were loaded:**

```text
specs/runs/REAL_RUN_TEMPLATE.md
specs/prompt-analysis-specs.md
skills/prompt-analysis.md
```

## Session isolation

- **Fresh session:** no
- **Previous related prompts in same session:** yes

## Spec ID

```text
Spec 005 - Good structured research prompt
```

## Input prompt

Paste the exact prompt sent to the model.

```text
Analyze this prompt using the fast analysis format from skills/prompt-analysis.md.

Research online pork belly products. Compare price per 100g, origin, seller reliability, reviews, shipping cost, and uncertainty. Exclude products with unclear source information. Output a ranked table and short buying recommendation.
```

## Raw model output

Paste the exact model response below, without edits, cleanup, rewriting, or summarization.

```text
### Verdict
good

### Why
- This is a research / product comparison prompt with clear comparison criteria: price per 100g, origin, seller reliability, reviews, shipping cost, and uncertainty.
- The exclusion rule for unclear source information gives it a practical quality boundary.

### Best part
It asks for a ranked table and short buying recommendation, so the output shape and decision goal are clear.

### Weak point
It should require source links/citations and a "date checked" field, because product listings, prices, reviews, and shipping costs change.

### Better version
Research online pork belly products. Compare price per 100g, origin, seller reliability, reviews, shipping cost, uncertainty, source link, and date checked. Exclude products with unclear source information. Output a ranked table and a short buying recommendation, marking unavailable or conflicting data as uncertain.
```

## Verbatim sanity check

- **Raw output line count:** 15
- **Raw output character count:** 899
- **Raw output was edited:** no

## Expected match

Paste the expected match criteria from the spec.

```text
Expected Analysis:
- Verdict: good
- Pattern: research / product comparison prompt
- Main strength: clear criteria and exclusion rule
- Main weakness: should add source citation requirement and date checked

Pass Criteria:
- Must identify criteria-based comparison
- Must suggest source/date tracking
```

## Evaluation

Compare the raw model output against the expected match. Keep this separate from the raw output.

```text
The raw model output matches the expected analysis.

It gives the verdict "good."
It identifies the pattern as "research / product comparison."
It identifies the criteria-based comparison by naming price per 100g, origin, seller reliability, reviews, shipping cost, and uncertainty.
It identifies the exclusion rule for unclear source information as a practical quality boundary.
It identifies the main weakness as missing source links/citations and a "date checked" field.
It suggests adding source link and date checked fields in the better version.
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
