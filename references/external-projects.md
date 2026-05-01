# External projects and reference map

## Why this file exists
- This repo combines a corpus of source-traceable prompt entries, a pattern lesson index, skill/workflow packaging, eval/spec runs, and a personal usage workflow.
- Most public projects cover only one layer. This map shows which layer each external source can inform, without treating any one project as the full system.

## Reference map

| External reference | Layer it informs | What to borrow | What not to copy | Status |
|---|---|---|---|---|
| Vanderbilt Prompt Pattern Catalog | Pattern catalog / pattern taxonomy | Reusable pattern framing, pattern composition idea | Do not replace repo-specific `PATTERN_LESSONS_INDEX` with academic taxonomy wholesale | Older than 2 years; useful but may be stale |
| AI-LLM/prompt-patterns | Pattern library implementation | YAML-like pattern organization, examples/counterexamples idea | Do not turn this repo into a generic pattern website | Adjacent reference |
| Anthropic Claude Skills docs | Skill packaging / operational instructions | Skill folder structure, `SKILL.md`, references/scripts/templates, progressive disclosure | Do not convert every current skill immediately; decide later whether `skills/` should migrate to folder-based format | High-value structural reference |
| Claude Skills overview | Personal/project skills and context management | Only load detailed instructions/resources when needed | Do not make the repo Claude-only | High-value structural reference |
| promptfoo | Evaluation / regression testing / red teaming | Declarative eval config, test cases, assertions, CI-quality gate idea | Do not adopt immediately without a small decision PR | Candidate for Phase 2 decision |
| promptimize | Prompt evaluation and variation testing | Prompt cases, eval functions, variations, suites | Do not add heavy tooling before manual run methodology is clearer | Adjacent eval reference |

## Design implications for this repo
- This repo is not redundant with any single reference found so far.
- It should preserve a four-layer distinction:
  1. corpus evidence
  2. pattern lessons
  3. operational skills/examples
  4. specs/real runs
- Phase 1 should still be `USAGE.md`.
- Phase 2 should include an explicit decision: manual real-run workflow vs `promptfoo`-style config.
- Skills folder migration to `SKILL.md`-style folders should be considered later, not mixed into this PR.

## Explicit non-goals
- Not a prompt marketplace
- Not a pure awesome-list
- Not an enterprise PromptOps SaaS clone
- Not a Claude-only skill pack
- Not a full academic taxonomy clone
