# Prompt Analysis Real Run 007

## Run metadata

- **Run ID:** prompt-analysis-real-run-007
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
Spec 007 - Strong output contract prompt
```

## Input prompt

Paste the exact prompt sent to the model.

```text
Analyze this prompt using the fast analysis format from skills/prompt-analysis.md.

Extract invoice_number, vendor_name, invoice_date, total_amount, and currency from the document. If a field is missing, return null. Output only valid JSON. Include evidence text for each field.
```

## Raw model output

Paste the exact model response below, without edits, cleanup, rewriting, or summarization.

```text
### Verdict
good

### Why
- This is an extraction / structured output prompt with a strong output contract: named fields, valid JSON only, and evidence text for each field.
- The null policy gives clear behavior when invoice data is missing instead of forcing guesses.

### Best part
The output contract is the strength: schema-like fields, missing-field handling, and evidence requirements make the extraction easier to validate.

### Weak point
It should define an explicit JSON schema, including how evidence is represented for each field and whether amounts/dates should be normalized.

### Better version
Extract invoice_number, vendor_name, invoice_date, total_amount, and currency from the document. Output only valid JSON matching this schema: {"invoice_number":{"value":string|null,"evidence":string|null},"vendor_name":{"value":string|null,"evidence":string|null},"invoice_date":{"value":string|null,"evidence":string|null},"total_amount":{"value":number|null,"evidence":string|null},"currency":{"value":string|null,"evidence":string|null}}. If a field is missing, set both value and evidence to null. Normalize invoice_date to YYYY-MM-DD when possible, total_amount as a number, and currency as ISO 4217.
```

## Verbatim sanity check

- **Raw output line count:** 15
- **Raw output character count:** 1215
- **Raw output was edited:** no

## Expected match

Paste the expected match criteria from the spec.

```text
Expected Analysis:
- Verdict: good
- Pattern: extraction / structured output
- Main strength: schema-like fields, null policy, evidence requirement
- Main weakness: could be stronger with explicit JSON schema

Pass Criteria:
- Must identify output contract as the strength
- Must mention null policy and evidence
```

## Evaluation

Compare the raw model output against the expected match. Keep this separate from the raw output.

```text
The raw model output matches the expected analysis.

It gives the verdict "good."
It identifies the pattern as "extraction / structured output."
It identifies the output contract as the main strength, including named schema-like fields and valid JSON output.
It explicitly mentions the null policy for missing invoice data.
It explicitly mentions evidence text and evidence requirements.
It identifies the main weakness as the lack of an explicit JSON schema.
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
```
