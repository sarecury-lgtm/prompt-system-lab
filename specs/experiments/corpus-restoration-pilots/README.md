# Corpus Restoration Pilots

## Question

Does the current corpus-backed Prompt Compiler improve final task results over a minimal request and a generic prompt improver, or does it mainly produce longer prompts?

## Compared variants

All variants must use the same execution model, tool availability, source materials, temperature/settings where controllable, and input case.

### A — minimal baseline

Preserve the user request with only a minimal execution wrapper. Do not add repository patterns.

### B — generic prompt improver

Ask the same model to rewrite the request into a good prompt using its general knowledge. Do not expose this repository, Pattern Lessons Index, active cards, or compiler routing.

### C — current Prompt Compiler

Use the current bundle and current routing policy exactly as shipped. Save the selected mode, patterns, active source, prompt, and routing record.

### D — source-derived candidate

Use only the named source-derived mechanism for the case family. Do not add every repository pattern.

- argument/comment analysis: PR085 claim decomposition candidate
- product comparison: PR106 uncertainty handling plus PR109 retrieval-first grounding candidate
- coding repair: PR088 inspect/plan/tool boundary plus PR091 deterministic edit boundary where applicable; PR093 only for genuinely multi-file completeness cases

D is not assumed to be superior. It tests whether a concrete source-derived mechanism contributes something beyond generic prompt improvement.

## Cases

`cases.jsonl` contains 15 fixed cases:

- 5 argument/comment analysis
- 5 product comparison
- 5 coding repair

Each family includes:

- normal
- ambiguous
- information-poor
- conflicting or adversarial
- long or complex

## Unit of evaluation

Evaluate the final task output produced after executing the generated prompt. Do not score prompt length, formatting polish, or apparent professionalism as quality by themselves.

## Core criteria

Use 0–2 anchors for each criterion:

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| intent preservation | changes the actual question | mostly preserves it with drift | preserves the real question and priority |
| condition retention | loses important constraints | retains some | retains all material constraints |
| unsupported inference | makes confident unsupported claims | mixes facts and inference | marks unknowns and separates inference |
| task-specific usefulness | generic or non-actionable | partly useful | directly supports the requested decision/action |
| unnecessary structure | structure obstructs the task | some avoidable burden | only structure that prevents a likely failure |
| robustness | breaks on ambiguity/conflict | partially handles it | handles it or asks the minimum necessary question |
| time/token burden | cost is disproportionate | some excess | cost is justified by useful contribution |

Total score is secondary. Reviewers must also record:

- decisive win or loss reason
- unique contribution, if any
- regression introduced
- whether the same benefit could be achieved with a shorter instruction

## Blinding

Where practical, remove variant labels and randomize output order before human review. The person judging outputs should not be told which one came from the repository.

## Promotion rule

A mechanism is not promoted because it wins one easy case.

- E3 requires a controlled local improvement with traceable outputs.
- E4 requires repeated improvement across cases, sessions, models, or evaluators.
- A task-specific win stays task-specific unless cross-task evidence exists.
- Higher token cost must be recorded as a tradeoff.

## Required artifacts per run

```text
runs/<run-id>/
  manifest.json
  prompts/
    <case-id>-A.txt
    <case-id>-B.txt
    <case-id>-C.txt
    <case-id>-D.txt
  routing/
    <case-id>-C.json
  outputs/
    <case-id>-A.md
    <case-id>-B.md
    <case-id>-C.md
    <case-id>-D.md
  blinded/
    <case-id>-mapping.json
  scores.csv
  kare-notes.md
  summary.md
```

## Stop condition

Do not change the runtime bundle during a run. Complete and review at least one full family before proposing a bundle change.
