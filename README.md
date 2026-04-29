# Personal Prompt System

A personal prompt-system repository for collecting prompt sources, extracting useful patterns, and turning them into reusable AI workflows.

This repo is meant to work like a small personal AI workspace:

- collect notable prompts and prompt sources
- analyze how they are structured
- rewrite weak prompts into practical versions
- keep project instructions and reusable skills in one place
- test whether analysis/rewrite behavior actually works

## Current Status

- Prompt corpus seed: PR001–PR100 complete
- Source index: created
- Project instructions: strengthened
- Skills added:
  - prompt analysis
  - prompt rewrite
  - corpus indexing
- Tests added:
  - prompt analysis tests
  - prompt rewrite tests

## Repository Structure

| Folder | Purpose |
|---|---|
| `project-instructions/` | Core operating instructions for this personal AI system |
| `prompt-corpus/` | Source-traceable prompt examples and prompt-pattern entries |
| `skills/` | Reusable workflows for analyzing, rewriting, and indexing prompts |
| `references/` | Source indexes, official docs, papers, and meta references |
| `tests/` | Manual test cases for checking prompt-system behavior |
| `archive/` | Old drafts, deprecated material, or messy notes |

## Key Files

| File | Purpose |
|---|---|
| `project-instructions/main.md` | Main operating rules for this project |
| `prompt-corpus/README.md` | Rules and navigation for the prompt corpus |
| `references/source-index.md` | Index showing where corpus batches live |
| `skills/prompt-analysis.md` | Skill for analyzing prompt quality and structure |
| `skills/prompt-rewrite.md` | Skill for rewriting prompts into usable versions |
| `skills/corpus-indexing.md` | Skill for adding sources, IDs, batches, and index updates |
| `tests/prompt-analysis-tests.md` | Manual tests for prompt analysis behavior |
| `tests/prompt-rewrite-tests.md` | Manual tests for prompt rewrite behavior |
| `changelog.md` | Project change history |

## Prompt Corpus

The first corpus batch is split into range files:

| Range | File |
|---|---|
| PR001–PR020 | `prompt-corpus/famous-prompts.md` |
| PR021–PR040 | `prompt-corpus/famous-prompts-pr021-pr040.md` |
| PR041–PR060 | `prompt-corpus/famous-prompts-pr041-pr060.md` |
| PR061–PR080 | `prompt-corpus/famous-prompts-pr061-pr080.md` |
| PR081–PR100 | `prompt-corpus/famous-prompts-pr081-pr100.md` |

## Operating Rules

- Keep source URLs traceable.
- Prefer short excerpts and structure summaries.
- Do not copy long copyrighted, paid, or proprietary prompt text.
- Store jailbreak/adversarial prompts only as history or defensive structure notes.
- Add new corpus batches by range.
- Update `references/source-index.md` when adding new batches.
- Turn repeated patterns into reusable skills.
- Add manual tests when a skill needs validation.

## Next Work

Likely next tasks:

1. Add PR101–PR150 with specialized Reddit/GitHub prompt sources.
2. Build a compact corpus summary table.
3. Add a source-collection skill for Reddit/GitHub research.
4. Run manual tests against `skills/prompt-analysis.md` and `skills/prompt-rewrite.md`.
