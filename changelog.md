# Changelog

## 2026-04-30

### Added

- Added `prompt-corpus/PATTERN_LESSONS_INDEX.md` as the practical entry point for using corpus-derived patterns.
- Added `skills/prompt-design-workflow.md` for turning rough user goals into usable prompts without overbuilding.
- Added a `Start Here` section to `README.md` so the repo is easier to use immediately.

### Changed

- Refreshed repository navigation to match the current corpus state through PR130.
- Updated `README.md` with:
  - PR001–PR130 corpus status
  - practical entry points for prompt design, rewrite, analysis, and indexing
  - `prompt-corpus/CORPUS_ENTRY_TEMPLATE.md`
  - representative Pattern lesson upgrades
  - source collection skill reference
- Updated `prompt-corpus/README.md` with:
  - PR101–PR120 and PR121–PR130 ranges
  - the upgraded entry field list
  - upgrade policy for representative entries
- Updated `references/source-index.md` with:
  - PR121–PR130 corpus file row
  - entry template row
  - system-prompt archive/index source family
  - current status through PR130
- Upgraded representative corpus entries into Pattern lesson format:
  - PR001 — Awesome ChatGPT Prompts
  - PR002 — Act as Linux Terminal
  - PR011 — Act as Prompt Enhancer
  - PR025 — ChatGPT DAN Repository

### Notes

- The corpus still contains many older seed-format entries. This is intentional for now.
- The next useful step is to expand `PATTERN_LESSONS_INDEX.md` with one representative pattern from each remaining source family.

## 2026-04-29

### Added

- Initialized the personal prompt-system repository structure.
- Added core folders:
  - `project-instructions/`
  - `prompt-corpus/`
  - `skills/`
  - `references/`
  - `tests/`
  - `archive/`
- Added prompt corpus seed entries PR001–PR100 across five files:
  - `prompt-corpus/famous-prompts.md`
  - `prompt-corpus/famous-prompts-pr021-pr040.md`
  - `prompt-corpus/famous-prompts-pr041-pr060.md`
  - `prompt-corpus/famous-prompts-pr061-pr080.md`
  - `prompt-corpus/famous-prompts-pr081-pr100.md`
- Added `prompt-corpus/README.md` for corpus rules and navigation.
- Updated `references/source-index.md` to map the PR001–PR100 corpus files.
- Strengthened `project-instructions/main.md` with operating style, tool routing, repository workflow, and user-experience rules.
- Strengthened `skills/prompt-analysis.md` with fast/full analysis modes, red flags, improvement moves, and tool-routing rules.
- Added `skills/prompt-rewrite.md` for rewriting messy prompts into usable prompt, project-instruction, and skill-lite formats.
- Added `skills/corpus-indexing.md` for ID rules, batch file rules, source quality tags, deduplication, and index updates.
- Updated `tests/prompt-analysis-tests.md` with 10 manual test cases for validating prompt-analysis behavior.

### Notes

- First corpus target complete: PR001–PR100.
- Current focus: turning raw prompt sources into a usable personal AI prompt-system workflow.
- Next likely work:
  - add PR101–PR150 specialized corpus entries
  - create a corpus summary/index table
  - add prompt-rewrite tests
  - add a workflow skill for Reddit/GitHub source collection
