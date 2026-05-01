# Prompt Analysis Real Run 003

## Run metadata

- **Run ID:** prompt-analysis-real-run-003
- **Date:** 2026-05-01
- **Runner:** Codex CLI session
- **Run type:** Real model run

## Model / environment

- **Model:** GPT-5 based Codex coding agent
- **Provider / interface:** OpenAI via Codex CLI
- **Model settings:** Default session settings
- **Relevant system or project instructions:** `skills/prompt-analysis.md` fast analysis format used for this prompt-analysis spec run
- **Environment notes:** Manual single-spec run for `specs/prompt-analysis-specs.md`

## Spec ID

```text
Spec 003 - Prompt enhancer meta-prompt
```

## Input prompt

```text
Analyze this prompt using the fast analysis format from skills/prompt-analysis.md.

Improve my prompt. Make it clearer, more specific, and more effective.
```

## Raw model output

```text
### Verdict
decent but underspecified

### Why
- This is a meta-prompt / prompt enhancer, but it does not say what kind of prompt is being improved or what success looks like.
- "Clearer, more specific, and more effective" are useful goals, but they need criteria: target task, audience, output format, constraints, and examples.

### Best part
It gives a clear improvement direction instead of asking for a vague rewrite.

### Weak point
It may produce a generic rewrite because it does not ask for the original prompt, intended use, audience, or constraints before editing.

### Better version
Before rewriting, ask me for:
1. the original prompt
2. the target task
3. the intended audience or user
4. the desired output format
5. constraints, examples, and failure cases

Then rewrite the prompt and briefly explain the most important changes.
```

## Expected match

```text
Expected Analysis:
- Verdict: decent but underspecified
- Pattern: meta-prompt / prompt enhancer
- Main weakness: no criteria for "better"
- Suggested fix: ask for target task, audience, output format, and constraints before rewriting

Pass Criteria:
- Must identify this as a meta-prompt
- Must not produce only a rewritten prompt without analysis
```

## Evaluation

```text
The raw model output matches the expected analysis.

It gives the verdict "decent but underspecified."
It explicitly identifies the prompt as a "meta-prompt / prompt enhancer."
It identifies the missing criteria for "clearer, more specific, and more effective."
It recommends asking for the target task, audience, output format, constraints, examples, and failure cases before rewriting.
It does not only produce a rewritten prompt; it provides analysis first and keeps the suggested better version as a follow-up structure.
```

## Result

```text
PASS
```

## Follow-up edit needed

```text
None.
```
