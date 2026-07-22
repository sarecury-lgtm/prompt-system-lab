# Task 002 — Restore Corpus Evidence Layers

## Objective

Reconnect PR001–PR130 to the evidence and promotion pipeline without putting the full corpus back into automatic runtime search.

## Constraints

- Do not delete, move, or bulk-rewrite existing corpus entries.
- Do not change `full_corpus_auto_search` during this task.
- Do not promote entries based on popularity, polish, or AI self-assessment.
- Treat current registry values as provisional.
- Preserve source traceability and copyright/safety boundaries.

## Progress — 2026-07-22

| Phase | Status | Evidence |
|---|---|---|
| A — inventory validation | manual pass complete; deterministic CI check committed but not yet run | `audit/corpus-registry-validation.md`, `scripts/validate_corpus_registry.py` |
| B — entry triage | priority pass complete for structured entries, evidence notes, runtime pattern sources, and all 7 active sources | `corpus/registry.csv` |
| C — runtime pattern audit | initial audit complete for all 9 patterns | `audit/runtime-pattern-evidence.csv` |
| D — pilot comparisons | cases, scoring, and variant contracts ready; model runs not yet completed | `specs/experiments/corpus-restoration-pilots/` |
| E — promotion decisions | blocked until pilot outputs and Kare Notes exist | none |

Current registry counts:

- reviewed: 10
- recovered: 4
- raw: 116
- tested: 0
- verified: 0
- rejected: 0

Current pattern grades:

- E1: 4
- E0: 5
- E2–E4: 0

The runtime bundle remains unchanged.

## Phase A — Inventory validation

For each row in `corpus/registry.csv`:

1. Open the corresponding range file.
2. Confirm that the ID exists exactly once.
3. Record the entry title and source URL status.
4. Check whether actual prompt text, a safe excerpt, or only a summary is present.
5. Replace provisional notes with evidence-based notes.

Deliverables:

- updated `corpus/registry.csv`
- duplicate, missing-ID, and malformed-entry report
- no status higher than evidence supports

## Phase B — Entry triage

Assign one of:

- `raw`
- `recovered`
- `reviewed`
- `tested`
- `verified`
- `rejected`
- `unavailable`

Use `corpus/CORPUS_STATUS_POLICY.md` as the contract.

Initial review order:

1. Entries already cited by the 9 runtime patterns
2. Entries already cited by the 7 active sources
3. Representative entries marked upgraded in README
4. High-value official or production sources
5. Remaining community and index entries

## Phase C — Runtime pattern evidence audit

For each of the 9 runtime patterns, create one row with:

- pattern ID
- claimed reusable move
- supporting entry IDs
- direct, partial, indirect, or missing support
- source-specific evidence
- synthesized or generic parts
- evidence grade E0–E4
- known boundary
- required next test

Deliverable:

`audit/runtime-pattern-evidence.csv`

Do not infer E3 or E4 from the existence of real-run files alone. Confirm that a controlled comparison and traceable outputs exist.

## Phase D — Three pilot comparisons

Run three task families:

1. argument/comment analysis
2. product comparison
3. coding repair

Compare under the same model and inputs:

- A: minimal baseline
- B: generic prompt improver without repository patterns
- C: current Prompt Compiler
- D: source-derived candidate when one exists

Use at least five inputs per task family:

- normal
- ambiguous
- information-poor
- conflicting or adversarial
- long or complex

Evaluate final task outputs, not prompt appearance.

Core criteria:

- intent preservation
- condition retention
- unsupported inference
- task-specific usefulness
- unnecessary structure
- robustness
- time and token burden

Record user judgment using Kare Notes.

## Phase E — Promotion decisions

After pilots:

- promote cross-task repeated improvements to general patterns
- keep task-specific improvements in `patterns/by-task/`
- keep domain-specific knowledge in `domains/`
- preserve failed ideas in negative lessons
- leave unclear candidates at `reviewed`
- mark `rejected` only with a recorded reason

## Runtime change gate

A new bundle version may be proposed only when:

- registry validation is complete for the entries used as evidence
- every included general pattern has an evidence grade
- pilot outputs are traceable
- the unique contribution over baseline and generic prompt generation is stated
- known regressions and cost are recorded

## Definition of done

- PR001–PR130 all exist in a validated registry
- no accidental deletion or duplicate ID remains unresolved
- 9 runtime patterns have evidence grades
- 3 pilot families have completed comparisons
- user Kare Notes are recorded
- a bundle change proposal is made only from the resulting evidence
