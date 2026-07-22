# Corpus Status and Evidence Policy

## Purpose

Preserve a broad source corpus and a narrow trusted runtime without treating unverified material as either proven or worthless.

This policy applies to PR001–PR130 and future prompt-source entries.

## Status values

### `raw`

The source is catalogued with enough metadata to find again, but its actual prompt mechanics have not been reviewed deeply.

Minimum evidence:

- stable entry ID
- source name or project
- source URL or recovery note
- short description

Runtime rule: never auto-apply.

### `recovered`

The actual prompt, a safe excerpt, or sufficiently detailed source material has been recovered.

Minimum evidence:

- all `raw` fields
- content location or excerpt note
- copyright and safety boundary

Runtime rule: never auto-apply.

### `reviewed`

A reviewer has identified the prompt's structure, mechanism, likely strengths, limitations, and applicable tasks.

Minimum evidence:

- mechanism
- use conditions
- failure mode
- reusable move or explicit reason not to extract one
- reviewer and date

Runtime rule: may inform research and candidate design, but not automatic promotion.

### `tested`

The prompt or extracted mechanism has been compared with a baseline using realistic inputs.

Minimum evidence:

- model and date
- baseline
- candidate prompt or pattern
- at least 3 inputs, including one difficult or ambiguous case
- raw outputs or traceable output locations
- result notes

Runtime rule: eligible for evidence grading.

### `verified`

A unique useful contribution was observed repeatedly, and limitations were recorded.

Minimum evidence:

- all `tested` evidence
- repeated improvement or strong external evidence plus local validation
- tasks where it helps
- tasks where it does not help
- cost or complexity tradeoff
- user judgment or independent evaluator note

Runtime rule: eligible for runtime promotion; promotion is still a separate decision.

### `rejected`

Review or testing found that the source or mechanism is misleading, unsafe, redundant, too costly, or ineffective for the intended use.

Required evidence:

- explicit rejection reason
- review or test reference
- any negative lesson worth preserving

Runtime rule: excluded.

### `unavailable`

The source cannot currently be recovered or checked.

Required evidence:

- last known source information
- recovery attempt or reason unavailable

Runtime rule: excluded pending recovery.

## Evidence grades for patterns

Pattern status and source-entry status are separate.

| Grade | Meaning |
|---|---|
| E0 | Plausible design hypothesis; no local corpus support established |
| E1 | Supported by one reviewed source entry |
| E2 | Repeated across multiple independent reviewed sources |
| E3 | Improved results in at least one controlled local comparison |
| E4 | Improved results across multiple tasks, inputs, sessions, or evaluators |

Default runtime guidance:

- E0–E1: do not include as a default general pattern
- E2: may be included as a cautious pattern with boundaries
- E3–E4: preferred runtime evidence level
- domain-specific evidence should remain a task or domain card rather than being promoted to a universal pattern

## Promotion path

```text
raw
→ recovered
→ reviewed
→ tested
→ verified
```

Entries may stop at any stage. They may also move to `rejected` or `unavailable` when evidence supports that status.

Promotion must not happen merely because:

- the source is popular
- the prompt is long or polished
- an AI says it looks good
- the source is official but no reusable contribution is established
- one easy example produced a good answer

## Runtime separation

The runtime bundle should contain only compact, selected material:

- routing policy
- sufficiently supported general patterns
- task-pattern index
- active or domain-card index
- global quality protocol
- negative constraints with evidence

The broad corpus remains outside automatic runtime search. It is used for discovery, source recovery, pattern research, and new skill development.

## Deletion policy

Do not delete a corpus entry merely because it is unverified, shallow, duplicated, or currently unused.

Preferred actions:

- mark status
- link duplicates
- preserve the strongest canonical source
- record why an item is not promoted
- archive only when navigation materially improves

Actual deletion requires a concrete reason such as accidental duplication with no unique metadata, sensitive content that should not be retained, or invalid generated material with no research value.
