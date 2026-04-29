# Prompt Corpus

## Purpose

This folder stores notable prompt sources and prompt-pattern examples worth studying, adapting, and testing.

The goal is not to blindly copy prompts. The goal is to collect source-traceable examples, summarize their structure, and turn useful patterns into reusable prompt-system components.

## Current Corpus

| Range | File | Focus | Status |
|---|---|---|---|
| PR001–PR020 | `famous-prompts.md` | Early ChatGPT prompt collections and “Act as…” role prompts | Seeded; PR001, PR002, PR011 upgraded |
| PR021–PR040 | `famous-prompts-pr021-pr040.md` | Programming prompts, academic prompts, jailbreak-history metadata, Reddit popular prompt lists, student prompt sources | Seeded; PR025 upgraded |
| PR041–PR060 | `famous-prompts-pr041-pr060.md` | Official prompt packs, media roundups, FlowGPT, OpenAI Community prompt threads, image prompt guides | Seeded |
| PR061–PR080 | `famous-prompts-pr061-pr080.md` | Official prompt libraries, prompt marketplaces, image prompt ecosystems, agent/template frameworks | Seeded |
| PR081–PR100 | `famous-prompts-pr081-pr100.md` | Fabric patterns, Cursor rules, coding-agent prompts, multi-agent frameworks, prompt indexes | Seeded |
| PR101–PR120 | `famous-prompts-pr101-pr120.md` | Reddit prompt threads, prompt-evaluation posts, PromptOps discussions, ChatGPT Project instruction discussions | Seeded |
| PR121–PR130 | `famous-prompts-pr121-pr130.md` | GitHub system-prompt indexes, official cookbook repos, prompt-engineering guide repos | Seeded |

## Entry Format

Use `CORPUS_ENTRY_TEMPLATE.md` when adding or upgrading corpus entries.

Each upgraded entry should include:

- ID
- Name
- Source URL
- Platform
- Type
- Source status
- Short excerpt
- Structure summary
- Pattern lesson
- Mechanism
- Failure mode
- Reusable move
- Tags
- Safety / reproduction note

## Upgrade Policy

The older seed format is acceptable for initial cataloging, but representative entries should be upgraded into the richer Pattern lesson format.

Prioritize upgrades for entries that teach a distinct design pattern, such as:

- role-prompt collections
- tool/interface emulation prompts
- meta-prompts and prompt improvers
- jailbreak-history sources
- official prompt libraries
- coding-agent/project-rule prompts
- PromptOps and evaluation discussions

A good upgraded entry should answer: “What prompt-design move can I reuse from this source?”

## Rules

- Keep source URLs traceable.
- Keep long prompt text out unless it is safe, necessary, and allowed.
- Prefer short excerpts and structure summaries.
- Jailbreak or adversarial prompts should be stored as history/structure notes only.
- Paid/proprietary prompts should be summarized, not copied.
- Add new batches by range, such as `famous-prompts-pr131-pr150.md`.
- Update `references/source-index.md` whenever a new batch is added.
- When upgrading entries, replace “Why it matters” with a concrete Pattern lesson, Mechanism, Failure mode, and Reusable move.

## Current Status

- Corpus complete through PR130.
- Upgraded template created.
- First representative upgrades complete: PR001, PR002, PR011, PR025.
- Next suggested direction:
  - upgrade one representative entry from each remaining source family
  - build a compact pattern summary table
  - add PR131–PR150 from Claude Skills, Cursor rules, coding-agent prompts, and prompt-eval resources
