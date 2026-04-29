# Prompt Corpus

## Purpose

This folder stores notable prompt sources and prompt-pattern examples worth studying, adapting, and testing.

The goal is not to blindly copy prompts. The goal is to collect source-traceable examples, summarize their structure, and turn useful patterns into reusable prompt-system components.

## Current Corpus

| Range | File | Focus |
|---|---|---|
| PR001–PR020 | `famous-prompts.md` | Early ChatGPT prompt collections and “Act as…” role prompts |
| PR021–PR040 | `famous-prompts-pr021-pr040.md` | Programming prompts, academic prompts, jailbreak-history metadata, Reddit popular prompt lists, student prompt sources |
| PR041–PR060 | `famous-prompts-pr041-pr060.md` | Official prompt packs, media roundups, FlowGPT, OpenAI Community prompt threads, image prompt guides |
| PR061–PR080 | `famous-prompts-pr061-pr080.md` | Official prompt libraries, prompt marketplaces, image prompt ecosystems, agent/template frameworks |
| PR081–PR100 | `famous-prompts-pr081-pr100.md` | Fabric patterns, Cursor rules, coding-agent prompts, multi-agent frameworks, prompt indexes |

## Entry Format

Each entry should include:

- ID
- Name
- Source URL
- Platform
- Type
- Short excerpt
- Structure summary
- Why it matters
- Tags
- Safety / reproduction note

## Rules

- Keep source URLs traceable.
- Keep long prompt text out unless it is safe, necessary, and allowed.
- Prefer short excerpts and structure summaries.
- Jailbreak or adversarial prompts should be stored as history/structure notes only.
- Paid/proprietary prompts should be summarized, not copied.
- Add new batches by range, such as `famous-prompts-pr101-pr120.md`.
- Update `references/source-index.md` whenever a new batch is added.

## Current Status

- First seed corpus complete: PR001–PR100.
- Next suggested direction: split future collection into specialized tracks:
  - Reddit prompt threads
  - GitHub prompt packs
  - image prompts
  - coding-agent prompts
  - meta-prompts and prompt-improvers
