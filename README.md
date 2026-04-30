# Personal Prompt System

A personal prompt-system repository for collecting prompt sources, extracting useful patterns, and turning them into reusable AI workflows.

This repo is meant to work like a small personal AI workspace:

- collect notable prompts and prompt sources
- analyze how they are structured
- rewrite weak prompts into practical versions
- keep project instructions and reusable skills in one place
- check whether analysis/rewrite behavior actually works
- upgrade raw source entries into reusable pattern lessons

## Start Here

If you want to actually use this repo, start with these files:

| Need | Use this file |
|---|---|
| Find a reusable prompt-design pattern | `prompt-corpus/PATTERN_LESSONS_INDEX.md` |
| Turn a rough goal into a usable prompt | `skills/prompt-design-workflow.md` |
| Rewrite an existing prompt | `skills/prompt-rewrite.md` |
| Analyze why a prompt is weak | `skills/prompt-analysis.md` |
| Add or organize new source entries | `skills/corpus-indexing.md` |
| Find where corpus batches live | `references/source-index.md` |


## Repository Structure

| Folder | Purpose |
|---|---|
| `project-instructions/` | Core operating instructions for this personal AI system |
| `prompt-corpus/` | Source-traceable prompt examples and prompt-pattern entries |
| `skills/` | Reusable workflows for analyzing, rewriting, and indexing prompts |
| `references/` | Source indexes, official docs, papers, and meta references |
| `specs/` | Manual specs for checking prompt-system behavior |
| `archive/` | Old drafts, deprecated material, or messy notes |

## Key Files

| File | Purpose |
|---|---|
| `project-instructions/main.md` | Main operating rules for this project |
| `prompt-corpus/README.md` | Rules and navigation for the prompt corpus |
| `prompt-corpus/PATTERN_LESSONS_INDEX.md` | Practical index of reusable prompt-design moves extracted from the corpus |
| `prompt-corpus/CORPUS_ENTRY_TEMPLATE.md` | Upgraded entry format for Pattern lesson, Mechanism, Failure mode, and Reusable move fields |
| `references/source-index.md` | Index showing where corpus batches live |
| `skills/prompt-design-workflow.md` | Skill for turning rough user goals into usable prompts |
| `skills/prompt-analysis.md` | Skill for analyzing prompt quality and structure |
| `skills/prompt-rewrite.md` | Skill for rewriting prompts into usable versions |
| `skills/corpus-indexing.md` | Skill for adding sources, IDs, batches, and index updates |
| `specs/prompt-analysis-specs.md` | Manual specs for prompt analysis behavior |
| `specs/prompt-rewrite-specs.md` | Manual specs for prompt rewrite behavior |
| `changelog.md` | Project change history |

## Prompt Corpus

The current corpus is split into range files:

| Range | File | Status |
|---|---|---|
| PR001–PR020 | `prompt-corpus/famous-prompts.md` | Seeded; representative entries PR001, PR002, PR011 upgraded |
| PR021–PR040 | `prompt-corpus/famous-prompts-pr021-pr040.md` | Seeded; representative entry PR025 upgraded |
| PR041–PR060 | `prompt-corpus/famous-prompts-pr041-pr060.md` | Seeded |
| PR061–PR080 | `prompt-corpus/famous-prompts-pr061-pr080.md` | Seeded |
| PR081–PR100 | `prompt-corpus/famous-prompts-pr081-pr100.md` | Seeded |
| PR101–PR120 | `prompt-corpus/famous-prompts-pr101-pr120.md` | Seeded |
| PR121–PR130 | `prompt-corpus/famous-prompts-pr121-pr130.md` | Seeded |

## Corpus Entry Direction

Older entries are useful as source catalog records, but the upgraded target format is more learning-oriented.

Each upgraded entry should explain:

- what source it came from
- how the prompt/source is structured
- what reusable prompt-design pattern it teaches
- why the pattern works
- how it can fail
- what compact design move can be reused elsewhere
- what safety or reproduction boundary applies

Use `prompt-corpus/CORPUS_ENTRY_TEMPLATE.md` when upgrading entries.

## Operating Rules

- Keep source URLs traceable.
- Prefer short excerpts and structure summaries.
- Do not copy long copyrighted, paid, or proprietary prompt text.
- Store jailbreak/adversarial prompts only as history or defensive structure notes.
- Add new corpus batches by range.
- Update `references/source-index.md` when adding new batches.
- Turn repeated patterns into reusable skills.
- Add manual tests when a skill needs validation.
- Upgrade representative raw entries into Pattern lesson format before trying to upgrade the whole corpus.

## Next Work

Likely next tasks:

1. Continue upgrading representative entries from PR041–PR130 into Pattern lesson format.
2. Expand `prompt-corpus/PATTERN_LESSONS_INDEX.md` with official-doc, evaluation, RAG, coding-agent, PromptOps, image-prompt, and multi-agent patterns.
3. Add PR131–PR150 with Claude Skills, Cursor rules, coding-agent prompt sources, and prompt-eval resources.
4. Run manual specs against `skills/prompt-design-workflow.md`, `skills/prompt-analysis.md`, `skills/prompt-rewrite.md`, and `skills/corpus-indexing.md`.
