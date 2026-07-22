# Corpus Restoration Audit — 2026-07-22

## Decision

The PR001–PR130 corpus was not deleted. It remains on `main` in seven range files and is still documented as the source-traceable corpus.

The actual problem is a layer break:

```text
PR001–PR130 source corpus
→ limited pattern extraction and verification
→ 9 runtime patterns + 7 active sources
→ full corpus excluded from normal runtime search
```

The verified-prompt track was intended to add a higher-trust path without replacing the broad corpus. In practice, the runtime path now uses only the compressed approved subset, while most source entries have no explicit status, evidence grade, or promotion path.

## Facts confirmed on main

### Broad corpus remains

- PR001–PR020: `prompt-corpus/famous-prompts.md`
- PR021–PR040: `prompt-corpus/famous-prompts-pr021-pr040.md`
- PR041–PR060: `prompt-corpus/famous-prompts-pr041-pr060.md`
- PR061–PR080: `prompt-corpus/famous-prompts-pr061-pr080.md`
- PR081–PR100: `prompt-corpus/famous-prompts-pr081-pr100.md`
- PR101–PR120: `prompt-corpus/famous-prompts-pr101-pr120.md`
- PR121–PR130: `prompt-corpus/famous-prompts-pr121-pr130.md`

### Runtime is deliberately narrow

`runtime/PROMPT_COMPILER_BUNDLE.md` currently contains:

- 9 general patterns
- 7 active sources
- `full_corpus_auto_search: false`
- `pattern_only_preferred: true`
- at most 1 active source per request

This is a reasonable runtime safety policy. It must not be interpreted as a judgment that the remaining corpus has no value.

### Existing evidence is incomplete

`prompt-corpus/PATTERN_VERIFICATION.md` already distinguishes:

- corpus-supported patterns
- partially corpus-supported patterns
- generic or synthesized parts of a reusable move
- source entries that still need excerpts or upgrades

Therefore, the repository already contains evidence that runtime patterns are not all equally established.

## Correct interpretation of corpus layers

| Layer | Meaning | Runtime use |
|---|---|---|
| raw | Source candidate with traceable metadata; not yet reviewed deeply | Never automatic |
| recovered | Actual prompt text or sufficient safe excerpt recovered | Never automatic |
| reviewed | Structure, mechanism, boundaries, and likely failure modes reviewed | Searchable for research |
| tested | Compared against a baseline on realistic inputs | Eligible for pattern evidence |
| verified | Repeated useful contribution established with limitations recorded | Eligible for runtime promotion |
| rejected | Tested or reviewed and found misleading, harmful, redundant, or ineffective | Excluded; lesson preserved |
| unavailable | Source cannot currently be recovered or checked | Excluded pending recovery |

`raw` does not mean useless. `rejected` requires an actual negative judgment with evidence.

## Root cause

The project correctly increased its verification standard, but did not create an explicit bridge between the broad corpus and the narrow runtime. That made “not verified for runtime” look like “not meaningful.”

The fix is not to re-enable full-corpus automatic search. The fix is to preserve the broad corpus as an intake and discovery layer, attach explicit statuses and evidence, and define a promotion path.

## Non-destructive restoration policy

1. Keep all PR001–PR130 entries in their current source files.
2. Do not move or rewrite all 130 entries at once.
3. Add status and evidence metadata through a registry.
4. Upgrade representative entries in batches.
5. Promote patterns only after source support and task-result evidence are recorded.
6. Keep failed candidates as negative lessons rather than deleting them.
7. Rebuild the runtime bundle only after pilot comparisons show a unique contribution.

## Next execution sequence

1. Create a corpus registry covering PR001–PR130.
2. Assign provisional status from existing repository evidence only.
3. Audit all 9 runtime patterns with an evidence grade.
4. Select three pilot tasks: argument analysis, product comparison, and coding repair.
5. Compare baseline, generic prompt generation, Prompt Compiler, and a source-derived candidate where available.
6. Record user judgment in Kare Notes.
7. Promote, narrow, or reject patterns based on the results.

## Completion criteria for restoration phase 1

- Every PR001–PR130 entry is represented in a registry.
- No entry is called rejected without a recorded review reason.
- Every runtime pattern points to source evidence and an evidence grade.
- Broad corpus and verified corpus are documented as complementary layers.
- Runtime remains narrow until pilot evidence justifies changes.
