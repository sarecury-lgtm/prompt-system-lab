# AI Review Packet

## Purpose

This file is a compact review packet for asking another AI to evaluate this repository without reading every corpus entry in full.

The repository is a personal prompt-system lab. It is not just a prompt list. It is meant to become a small reusable AI workflow system with:

- prompt source corpus
- reusable skills
- project-level operating instructions
- tests for prompt analysis and rewriting
- source index and changelog

## What This Repo Is Trying To Become

A personal AI prompt workspace that can:

1. collect famous, useful, controversial, or structurally interesting prompts
2. summarize how those prompts are built
3. extract reusable design patterns
4. turn those patterns into skills and project instructions
5. test whether those skills actually work
6. stay easy enough for one user to operate

## Current State

### Done

- GitHub repo created and connected.
- Basic folder structure created.
- Prompt corpus PR001–PR120 created.
- Source index created and updated.
- Main project instructions written.
- Prompt analysis skill created.
- Prompt rewrite skill created.
- Corpus indexing skill created.
- Source collection skill created.
- Manual tests for prompt analysis created.
- Manual tests for prompt rewrite created.
- README and changelog updated.

### Partially done

- PR121–PR130 was added as a smaller split batch after a longer PR121–PR140 write failed.
- PR131–PR140 has not been added yet.

### Not done yet

- No automated tests.
- No compact master table of all PR001–PR120 entries.
- No actual run results from the manual tests.
- No synthesis report extracting patterns from the collected prompts.
- No final ChatGPT Project instruction file ready to paste into ChatGPT Projects.

## Important Files To Read First

Read these in order:

1. `README.md`
   - overall repo purpose and structure

2. `project-instructions/main.md`
   - operating behavior for the personal AI system

3. `references/source-index.md`
   - map of all corpus files and skills

4. `skills/prompt-analysis.md`
   - reusable workflow for analyzing prompts

5. `skills/prompt-rewrite.md`
   - reusable workflow for rewriting prompts

6. `skills/corpus-indexing.md`
   - rules for adding corpus entries

7. `skills/source-collection.md`
   - rules for collecting sources

8. `tests/prompt-analysis-tests.md`
   - manual test cases for analysis behavior

9. `tests/prompt-rewrite-tests.md`
   - manual test cases for rewrite behavior

10. `prompt-corpus/README.md`
   - corpus organization rules

Only read the full corpus files if you need examples.

## Prompt Corpus Files

| Range | File | Focus |
|---|---|---|
| PR001–PR020 | `prompt-corpus/famous-prompts.md` | early ChatGPT prompt collections and “Act as…” prompts |
| PR021–PR040 | `prompt-corpus/famous-prompts-pr021-pr040.md` | programming, academic, jailbreak-history, Reddit, student prompt sources |
| PR041–PR060 | `prompt-corpus/famous-prompts-pr041-pr060.md` | official prompt packs, media roundups, FlowGPT, OpenAI Community, image prompt guides |
| PR061–PR080 | `prompt-corpus/famous-prompts-pr061-pr080.md` | Anthropic/OpenAI guides, prompt marketplaces, image prompt ecosystems, agent frameworks |
| PR081–PR100 | `prompt-corpus/famous-prompts-pr081-pr100.md` | Fabric, Cursor rules, coding agents, multi-agent frameworks |
| PR101–PR120 | `prompt-corpus/famous-prompts-pr101-pr120.md` | Reddit/community prompt threads, PromptOps, evaluation, versioning, project instruction discussions |
| PR121–PR130 | `prompt-corpus/famous-prompts-pr121-pr130.md` | GitHub prompt-engineering indexes and official repositories |

## How To Evaluate This Repo

Please evaluate the repository on these dimensions:

1. **Clarity**
   - Is the repo purpose clear?
   - Can a new AI understand what to do from the files?

2. **Structure**
   - Are folders and files named well?
   - Is the corpus split in a useful way?

3. **Usefulness**
   - Does this help build a personal prompt system, or is it just a pile of links?

4. **Completeness**
   - What is missing before this becomes useful in practice?

5. **Overengineering**
   - Is anything too complex for one user?
   - Should any files be merged, simplified, or removed?

6. **Corpus quality**
   - Are the source categories useful?
   - Are there too many weak/secondary sources?
   - What should the next 50 entries focus on?

7. **Skill quality**
   - Are `prompt-analysis.md`, `prompt-rewrite.md`, `corpus-indexing.md`, and `source-collection.md` useful as reusable workflows?
   - Are they too long or vague?

8. **Testing**
   - Are the manual tests enough?
   - What would be the minimum useful automated test setup?

9. **User experience**
   - Does the repo support a simple assistant-like workflow?
   - Is it clear what the user should do next?

10. **Next actions**
   - Give the top 5 changes that would most improve the repo.

## Specific Questions For Another AI

Ask another AI something like this:

```text
I am building a personal prompt-system repository. Please review the repo using AI_REVIEW_PACKET.md as the entry point.

Focus on:
1. whether the structure is good
2. whether it is becoming useful or just bloated
3. what files should be simplified
4. what should be built next
5. how I should actually use this in ChatGPT Projects or another AI tool

Do not summarize every corpus entry. Give practical improvement advice.
```

## How This Repo Should Be Used

### For daily use

Use the repo as a reference system:

- when analyzing a prompt, read `skills/prompt-analysis.md`
- when rewriting a prompt, read `skills/prompt-rewrite.md`
- when adding sources, follow `skills/corpus-indexing.md` and `skills/source-collection.md`
- when checking what exists, read `references/source-index.md`

### For ChatGPT Projects

The most useful file to paste or adapt into ChatGPT Project instructions is:

- `project-instructions/main.md`

But it may need a shorter copy-paste version later.

### For another AI review

Give it:

- this `AI_REVIEW_PACKET.md`
- `README.md`
- `project-instructions/main.md`
- `references/source-index.md`
- all files under `skills/`
- test files if it needs to judge quality

Avoid giving it all corpus files at once unless the model can handle long context.

## Current Recommended Next Step

Stop expanding the corpus for a moment.

Before adding more entries, create:

1. `PROJECT_USAGE_GUIDE.md`
   - explains how the user actually uses the repo

2. `PROJECT_INSTRUCTIONS_COMPACT.md`
   - a short paste-ready ChatGPT Project instruction

3. `CORPUS_SUMMARY.md`
   - one-page summary of what PR001–PR130 teaches

4. Run manual tests once and record failures.
