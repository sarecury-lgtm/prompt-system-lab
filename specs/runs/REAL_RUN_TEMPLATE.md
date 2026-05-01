# Real Spec Run Template

## Run metadata

- **Run ID:**
- **Date:**
- **Runner:**
- **Evaluator:**
- **Runner = evaluator:** yes / no
- **Run type:** Real model run
- **Run count N:**
- **Evidence type:** single-run evidence / repeated evidence

## Model / environment

- **Model:**
- **Model identifier / exact model string:**
- **Release date or version:**
- **Provider / interface:**
- **Sampling settings:**
  - **temperature:**
  - **top_p:**
  - **max_tokens:**
- **Relevant system or project instructions:**
- **Environment notes:**

## Context injection

- **Skill/spec content actually loaded:** yes / no / partial
- **Injection method:** full paste / file-system access / RAG / other
- **Which files were loaded:**

```text

```

## Session isolation

- **Fresh session:** yes / no
- **Previous related prompts in same session:** yes / no

## Spec ID

```text

```

## Input prompt

Paste the exact prompt sent to the model.

```text

```

## Raw model output

Paste the exact model response below, without edits, cleanup, rewriting, or summarization.

```text

```

## Verbatim sanity check

- **Raw output line count:**
- **Raw output character count:**
- **Raw output was edited:** yes / no

## Expected match

Paste the expected match criteria from the spec.

```text

```

## Evaluation

Compare the raw model output against the expected match. Keep this separate from the raw output.

```text

```

## Result

Choose one: PASS / PARTIAL / FAIL

- **PASS:** Raw output satisfies all required expected-match criteria, with no material contradiction or missing required behavior.
- **PARTIAL:** Raw output satisfies some required criteria, but misses, weakens, or ambiguously handles at least one material expected-match criterion.
- **FAIL:** Raw output misses the core expected behavior, contradicts required criteria, or cannot be evaluated because the captured output is incomplete or not verbatim.

```text

```

## Follow-up edit needed

```text

```
