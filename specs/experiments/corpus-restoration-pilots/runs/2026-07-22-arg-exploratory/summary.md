# Exploratory Summary — Argument / Comment Analysis

## Verdict

The current Prompt Compiler did **not** show a general advantage over the minimal baseline in this five-case exploratory run.

The strongest visible corpus-derived contribution came from the PR085-style claim-decomposition candidate, especially when the input contained multiple speakers, reply chains, or several easily conflated claims.

This run is not blinded, independent, or promotion-eligible. The scores are diagnostic notes, not proof.

## Provisional scores

Maximum: 14 per case.

| Variant | Mean | Range | Exploratory interpretation |
|---|---:|---:|---|
| A — minimal baseline | 13.2 | 12–14 | already strong; often sufficient for short or information-poor disputes |
| B — generic improver | 12.0 | 12–12 | usually added format and procedure without a visible substantive gain |
| C — current Prompt Compiler | 12.0 | 12–12 | improved explicit fields and uncertainty labels, but frequently over-structured simple cases |
| D — PR085 candidate | 13.6 | 13–14 | clearest claim/rebuttal mapping; advantage concentrated in multi-turn and complex cases |

Scores should not be interpreted as precise model-performance measurements. The same model generated, executed, and reviewed all variants in one session.

## Case-level findings

### Short single-claim case

A already identified the temporal-causality error, hidden assumptions, and alternative explanations. C added a stable table and verification fields, but did not change the conclusion. D more explicitly separated opportunity, name similarity, and actual copying, though the gain was modest.

### Ambiguous two-comment case

A and D both reached the correct narrow conclusion: popularity does not establish truth, while the original factual question remains unknown. B and C were correct but heavier.

### Information-poor statistical dispute

All variants avoided inventing a statistic. A and D handled the missing-evidence boundary without needing a large schema. C's confirmed/claim/evidence/verification table was clear but not uniquely necessary.

### Adversarial reply chain

D produced the clearest unique behavior: it mapped each statement to the exact earlier claim it answered, separated A's valid criticism from A's later diversion, and showed that B's final accusation was only partly applicable. A reached a similar conclusion, but less systematically.

### Long multi-party thread

D best separated five nearby but non-equivalent claims: reported incidents, actual crime, reporting rate, population/measurement comparability, and the interpretation of an official source. C was reliable and explicit but incurred the most structural burden. A was substantively good but compressed the reply graph.

## What this says about the current system

1. A strong base model can already perform much of the generic argument analysis without repository patterns.
2. Generic prompt improvement is not a useful control-group winner here; it mainly made prompts look more formal.
3. The current Compiler's common patterns improved consistency and visible uncertainty handling, but those gains did not outweigh extra structure in short cases.
4. PR085's useful contribution is not “analyze critically.” It is the narrower mechanism: preserve claim units and connect each reply to the exact claim it addresses.
5. That mechanism appears task-specific. This run does not justify promoting it as a universal pattern.

## Decision

- Do not alter the runtime bundle from this run.
- Do not assign E3 to PR085 or any current pattern.
- Keep PR085 as a candidate for `patterns/by-task/argument-analysis`.
- Before promotion, conduct a blinded review of these outputs and collect Kare Notes.
- A future compact task pattern should trigger mainly for multi-party, long, nested, or claim-dense argument analysis—not every short opinion question.

## Candidate compact mechanism

```text
When an argument contains multiple claims or replies, split each speaker's statements into claim units and connect each reply to the exact prior claim it addresses. Separate stated evidence, hidden assumptions, support range, alternative explanations, and external facts that still require verification. Do not add this structure to a simple single-claim question unless it prevents a specific ambiguity.
```

## Main negative lesson

“More explicit analysis fields” is not itself a unique contribution. If the baseline already preserves the question, marks uncertainty, and reaches the same judgment, the added template is overhead rather than improvement.
