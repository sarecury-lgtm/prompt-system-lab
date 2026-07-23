# Pilot Synthesis — 2026-07-23

## Scope

Exploratory A/B/C/D runs now exist for all three task families:

- argument/comment analysis: 5 cases
- product comparison: 5 cases, including 2 source-backed exact-product cases
- coding repair: 4 continuation cases plus the normal login fixture

All runs are same-session and unblinded. They support routing hypotheses, not E3/E4 promotion.

## Cross-family result

The winning design is not a universally larger prompt. It is a baseline-first router with narrow failure-triggered additions.

| Task condition | Best current direction |
|---|---|
| Clear short request; base model already preserves intent | baseline |
| Missing products/configurations block comparison | compact one-batch clarification |
| Multi-speaker, nested, claim-dense argument | claim-linking task pattern |
| Current product facts or exact SKU/market/price comparison | source-validation task pattern |
| Simple isolated code failure with a clear test | baseline + actual test execution |
| Reported incident not reproduced | evidence-before-edit task pattern |
| Cross-file API/type/config/migration risk | smallest-complete-change task pattern |

## Family findings

### Argument analysis

- Baseline was already strong on short and information-poor disputes.
- General Compiler structure often increased output burden without changing judgment.
- PR085-style claim linking added value only on nested or claim-dense threads.

### Product comparison

- Compiler and grounded candidate clearly outperformed when sources were internally inconsistent or configuration-dependent.
- The useful mechanism was identity/configuration/market/method validation, not more comparison columns.
- A result on an official domain can still be unusable when page content does not match the named product.

### Coding repair

- Baseline matched C/D on isolated observable failures.
- Generic improvement caused unnecessary behavior changes despite passing visible tests.
- C/D added value when the correct action was no patch or when completeness required multiple files.

## Proposed routing policy

```text
1. Start from a preserved minimal baseline.
2. Identify a concrete failure that baseline is likely to make.
3. Add at most one task pattern whose behavior directly prevents that failure.
4. Do not activate a pattern merely because the task belongs to its broad category.
5. Remove the pattern when it only adds fields, explanation, or ceremony.
6. Keep domain/market/source identity checks separate from universal response rules.
```

## Evidence decision

- No runtime general pattern moves to E3 or E4.
- PR085, PR106, and PR109 have local comparison evidence sufficient to call their extracted mechanisms `tested candidates`, but not verified.
- PR088 has multi-case workflow evidence, but its source entry still needs a stronger source-specific review before source-level promotion.
- PR093 showed value on one cross-file fixture; more inputs are required before `tested` status.

## Runtime decision

Do not widen `full_corpus_auto_search` and do not replace the current bundle in this PR.

A future bundle proposal should add only a compact task-pattern index and routing boundaries after blinded review and Kare Notes confirm these findings.
