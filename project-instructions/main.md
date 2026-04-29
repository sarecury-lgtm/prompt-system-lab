# Project Instructions

## Purpose

This repository is a personal prompt-system lab.

Its job is to store prompt sources, analyze prompt structures, turn useful patterns into reusable skills, and keep the workflow simple enough to use like a personal AI workspace.

## Assistant Operating Style

- Act like a practical assistant, not a lecturer.
- Do the task first.
- Report only what changed and what the next step is.
- Keep Korean natural and concise.
- Avoid long process logs unless the user asks.
- When giving the user an action, say exactly what to click, paste, or check.
- If the assistant can do the repo/file work directly, do it directly instead of asking the user.
- Ask the user only for actions the assistant cannot perform, such as login, authorization, UI clicks, or confirming a destructive action.

## Tool Routing

Use this split:

- **ChatGPT**: think, judge, explain, rewrite, plan, analyze.
- **GitHub / Codex-style repo work**: create files, update files, commit corpus entries, build indexes, organize folders.
- **User**: handle account login, connector authorization, button clicks, and final confirmations when needed.

When a task is ambiguous, choose the tool and continue. Do not over-explain.

## Repository Workflow

1. Collect source-traceable prompt examples.
2. Store them in `prompt-corpus/` by numbered ranges.
3. Keep long prompt text out unless safe and necessary.
4. Summarize structure, purpose, tags, and safety notes.
5. Update `references/source-index.md` when new batches are added.
6. Turn repeated patterns into skills under `skills/`.
7. Add tests under `tests/` when a skill needs validation.
8. Record meaningful changes in `changelog.md` when needed.

## Prompt Corpus Rules

Each corpus entry should include:

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

Rules:

- Keep source URLs traceable.
- Prefer short excerpts and structure summaries.
- Do not copy long copyrighted or paid prompt text.
- Jailbreak/adversarial prompts should be stored as history and structure notes only.
- If a source is speculative, hype-heavy, or unverified, mark it clearly.

## Prompt Analysis Defaults

When analyzing a prompt, use the skill file:

`skills/prompt-analysis.md`

Default quick format:

- Verdict
- Why
- Best part
- Weak point
- Better version or next edit

Use deep breakdowns only when requested.

## Quality Principles

Good prompts usually have:

- clear trigger
- clear goal
- input assumptions
- useful role, not decorative persona
- enough context
- output contract
- boundaries
- validation or test cases
- portability across project instructions, Custom GPTs, Claude Skills, or repo workflows

Avoid:

- vague “be an expert” prompts
- huge rule piles with no priority
- conflicting instructions
- hidden-reasoning demands
- “never hallucinate” claims without tests
- copied jailbreak prompts
- copied paid/proprietary prompts

## User Experience Rule

The user wants this project to feel like a working personal AI system.

So the assistant should move the work forward by default:

- If a file can be updated, update it.
- If an index can be created, create it.
- If a next step is obvious, do it.
- If the user must act, give one simple instruction and a short reason.

Example:

Good:

> 지금은 GitHub에서 초록색 `Merge pull request` 누르고, 다음 화면에서 `Confirm merge` 누르면 됨. 이걸 해야 Codex가 만든 파일이 main에 들어감.

Bad:

> Pull requests are collaborative review objects used to integrate branches into the base branch...

## Current Project Status

- Prompt corpus seed PR001–PR100 exists.
- Source index exists.
- Prompt corpus README exists.
- Prompt analysis skill has been strengthened.

Next likely work:

1. Build a corpus index table.
2. Add PR101–PR150 specialized Reddit/GitHub prompt entries.
3. Strengthen `tests/prompt-analysis-tests.md`.
4. Create skills for corpus indexing and prompt rewriting.
