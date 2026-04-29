# AI Review Bundle — Compact

## What this is

This is a compact, paste-ready review bundle for another AI.

The full repo is `sarecury-lgtm/prompt-system-lab`, a private GitHub repository for building a personal prompt-system workspace.

It is meant to become a small personal AI operating system for prompt work, not just a prompt list.

## Review request

Please review this personal prompt-system project.

Focus on:

1. Is the structure useful or overbuilt?
2. Is this becoming a usable personal AI system, or just a pile of prompt links?
3. Which files should be simplified, merged, or deleted?
4. What should be built next?
5. How should this be used inside ChatGPT Projects, Claude Projects, or a Custom GPT?

Do not summarize every corpus entry. Give practical improvement advice.

## Current repo state

Done:

- Repo created and connected to GitHub.
- Folder structure created.
- Prompt corpus entries PR001–PR130 added.
- Source index created and updated.
- Main project instructions written.
- Prompt analysis skill created.
- Prompt rewrite skill created.
- Corpus indexing skill created.
- Source collection skill created.
- Manual tests for prompt analysis created.
- Manual tests for prompt rewrite created.
- README and changelog updated.

Partially done:

- PR121–PR130 exists.
- PR131–PR140 failed when attempted as a long batch, so it has not been added yet.

Not done:

- No automated tests.
- No compact master table of all entries.
- No actual test run results.
- No final paste-ready ChatGPT Project instruction.
- No synthesis report explaining what the corpus teaches.

## Folder structure

```text
prompt-system-lab/
  README.md
  AI_REVIEW_PACKET.md
  AI_REVIEW_BUNDLE_COMPACT.md
  changelog.md
  project-instructions/
    main.md
  prompt-corpus/
    README.md
    famous-prompts.md
    famous-prompts-pr021-pr040.md
    famous-prompts-pr041-pr060.md
    famous-prompts-pr061-pr080.md
    famous-prompts-pr081-pr100.md
    famous-prompts-pr101-pr120.md
    famous-prompts-pr121-pr130.md
  references/
    source-index.md
  skills/
    prompt-analysis.md
    prompt-rewrite.md
    corpus-indexing.md
    source-collection.md
  tests/
    prompt-analysis-tests.md
    prompt-rewrite-tests.md
  archive/
    README.md
```

## Important files

### `README.md`

The repo’s front page. It explains:

- repo purpose
- current status
- folder structure
- key files
- corpus ranges
- operating rules
- next work

### `AI_REVIEW_PACKET.md`

The main review guide for another AI.

It tells the reviewer:

- what the repo is trying to become
- what is done / partial / missing
- which files to read first
- how to evaluate the repo
- what questions to answer

### `project-instructions/main.md`

Main operating rules for the personal AI system.

Core ideas:

- act like a practical assistant, not a lecturer
- do the task first
- report only what changed and next step
- use natural concise Korean
- do repo/file work directly when possible
- ask the user only for UI/login/authorization/destructive-confirmation actions
- route work like this:
  - ChatGPT: think, judge, explain, rewrite, plan, analyze
  - GitHub/Codex-style work: create files, update files, organize repo
  - User: login, authorization, button clicks, final confirmations when needed

### `references/source-index.md`

Navigation index for corpus files, skills, tests, and source families.

Current corpus ranges:

| Range | File | Focus |
|---|---|---|
| PR001–PR020 | `prompt-corpus/famous-prompts.md` | early ChatGPT prompt collections and “Act as…” prompts |
| PR021–PR040 | `prompt-corpus/famous-prompts-pr021-pr040.md` | programming, academic, jailbreak-history, Reddit, student prompt sources |
| PR041–PR060 | `prompt-corpus/famous-prompts-pr041-pr060.md` | official prompt packs, media roundups, FlowGPT, OpenAI Community, image prompt guides |
| PR061–PR080 | `prompt-corpus/famous-prompts-pr061-pr080.md` | official prompt libraries, marketplaces, image ecosystems, agent/template frameworks |
| PR081–PR100 | `prompt-corpus/famous-prompts-pr081-pr100.md` | Fabric, Cursor rules, coding agents, multi-agent frameworks |
| PR101–PR120 | `prompt-corpus/famous-prompts-pr101-pr120.md` | Reddit/community prompt threads, PromptOps, evaluation, versioning, project instruction discussions |
| PR121–PR130 | `prompt-corpus/famous-prompts-pr121-pr130.md` | GitHub prompt-engineering indexes and official repositories |

### `skills/prompt-analysis.md`

Reusable workflow for analyzing prompt quality.

It checks:

- trigger
- goal
- input
- role
- context
- routing
- criteria
- output contract
- boundaries
- validation
- portability

Default fast output:

- Verdict
- Why
- Best part
- Weak point
- Better version or next edit

### `skills/prompt-rewrite.md`

Reusable workflow for rewriting weak prompts.

Rewrite modes:

- Clean Prompt
- Strong Prompt
- Project Instruction
- Skill-Lite
- Compact Version
- Defensive Rewrite

Core rule:

- rewrite first, explain briefly after
- preserve the user’s real goal
- do not strengthen jailbreaks or unsafe prompts

### `skills/corpus-indexing.md`

Rules for keeping the corpus organized.

It defines:

- ID rules: PR###, C###, G###, P###, O###
- batch file rules
- entry template
- quality tags
- safety rules
- deduplication rules
- index update rules

### `skills/source-collection.md`

Rules for collecting source material.

Collection priority:

1. actual prompt text / prompt packs / prompt repos
2. famous or controversial community threads
3. official prompt packs or vendor guides
4. GitHub repos with prompt templates/system prompts/agent prompts
5. papers/surveys with named techniques and examples
6. blogs/media only if they reflect popular usage or point to useful sources

### `tests/prompt-analysis-tests.md`

Manual test cases for analysis behavior.

Includes 10 cases:

- vague expert role prompt
- tool simulation prompt
- prompt enhancer meta-prompt
- overbuilt prompt
- structured research prompt
- jailbreak-style prompt
- structured extraction prompt
- style-only prompt
- project instruction prompt
- agent workflow prompt

### `tests/prompt-rewrite-tests.md`

Manual test cases for rewrite behavior.

Includes 10 cases:

- vague explanation prompt
- decorative expert role
- research prompt
- project instruction style
- skill-lite conversion
- unsafe jailbreak prompt
- overbuilt prompt
- stock chart prompt
- translation prompt
- too-long prompt

## Corpus philosophy

The corpus is not meant to copy prompts blindly.

Each entry stores:

- ID
- name
- source URL
- platform
- type
- short excerpt
- structure summary
- why it matters
- tags
- safety / reproduction note

Rules:

- keep source URLs traceable
- prefer summaries over long copied text
- do not copy paid/proprietary prompts in full
- jailbreak/adversarial prompts should be history/defense notes only
- mark unverified or hype-heavy claims clearly

## Main concern

The project is starting to become useful, but it risks becoming a large archive before it becomes an easy-to-use system.

Recommended pause point:

Stop expanding the corpus for a moment and build usability files.

## Recommended next files

1. `PROJECT_USAGE_GUIDE.md`
   - explains how the user actually uses the repo day to day

2. `PROJECT_INSTRUCTIONS_COMPACT.md`
   - short paste-ready ChatGPT Project instruction

3. `CORPUS_SUMMARY.md`
   - what PR001–PR130 teaches, summarized by patterns

4. `TEST_RUN_REPORT.md`
   - run manual tests once and record what failed

## Questions for reviewer

Please answer:

1. Is this repo structure sensible?
2. Is the project overbuilt for a single user?
3. Which files are most valuable?
4. Which files should be simplified?
5. Should corpus expansion pause until usage files are made?
6. What would be the best compact project instruction for ChatGPT?
7. How would you turn this into a more Claude-like assistant workflow?
8. What are the top 5 concrete next changes?
