# Skill: Corpus Indexing

## Purpose

Keep prompt sources organized, traceable, and easy to reuse.

Use this skill when adding new prompt sources, Reddit threads, GitHub repositories, official guides, papers, prompt marketplaces, image prompts, coding-agent prompts, or community examples to the repository.

## Operating Style

- If the assistant can update files directly, do it directly.
- Do not ask the user to copy/paste unless a UI action is required.
- Keep progress reports short.
- Always preserve source traceability.
- Do not let entries stop at metadata. Each useful entry should teach at least one reusable pattern.

## Folder Targets

Use these folders:

- `prompt-corpus/` for prompt source entries and prompt pattern examples.
- `references/` for source indexes, official docs, papers, and meta references.
- `skills/` for reusable workflows.
- `tests/` for validation examples.
- `archive/` for old, superseded, or messy drafts.

## ID Rules

Use stable IDs.

### Prompt corpus

Use `PR###` IDs.

Examples:

- PR001
- PR020
- PR100
- PR101

### Community debates

Use `C###` IDs only when the corpus clearly splits into a dedicated community-debate track.

Examples:

- C001 for Reddit/Hacker News/community discussion threads.

### GitHub / tools / skills

Use `G###` IDs only when the corpus clearly splits into a dedicated tools/repo track.

Examples:

- G001 for GitHub tools, repos, prompt libraries, or skill packages.

### Papers / academic sources

Use `P###` IDs only when the corpus clearly splits into a dedicated paper/research track.

Examples:

- P001 for papers, surveys, and research reports.

### Official docs

Use `O###` IDs only when the corpus clearly splits into a dedicated official-docs track.

Examples:

- O001 for official vendor docs and platform guides.

### Current rule

Do not create new ID families too early. Until the corpus actually needs separation, continue with `PR###` and use tags for source type.

## Batch File Rules

Do not put everything into one huge file.

Use range files:

- `famous-prompts.md` for PR001–PR020
- `famous-prompts-pr021-pr040.md`
- `famous-prompts-pr041-pr060.md`
- `famous-prompts-pr061-pr080.md`
- `famous-prompts-pr081-pr100.md`
- future: `famous-prompts-pr101-pr120.md`

For specialized tracks, use separate files only when the topic is large enough:

- `reddit-prompt-threads-c001-c050.md`
- `github-prompt-packs-g001-g050.md`
- `image-prompts-pr-image-001.md`
- `coding-agent-prompts.md`
- `meta-prompts.md`

## Entry Template

Each entry should include:

```markdown
### PR###
- **ID:** PR###
- **Name:** [name]
- **Source URL:** [url]
- **Platform:** [platform]
- **Type:** [type]
- **Short excerpt:** [one short description or tiny excerpt]
- **Structure summary:** [how it is built]
- **Why it matters:** [why this source is worth keeping]
- **Pattern lesson:** [what reusable design pattern, failure pattern, or prompt-system lesson this source teaches]
- **Tags:** `tag1`, `tag2`, `tag3`
- **Safety / reproduction note:** [what not to copy or how to handle safely]
```

## Field Meanings

### Short excerpt

A short source-facing description or tiny quote when allowed.

Bad:

> A useful prompt.

Good:

> Requests the model to emulate shell I/O behavior.

### Structure summary

Describe the prompt/source architecture.

Bad:

> It is structured well.

Good:

> Defines strict terminal-only output, then repeats command-response turns.

### Why it matters

Explain why the source is worth keeping in the corpus.

Bad:

> Important example.

Good:

> Canonical early example of using role and output constraints to simulate an interface.

### Pattern lesson

Explain what can be reused, avoided, or tested later.

This is the most important field for turning a catalog into learning material.

Bad:

> This teaches prompt engineering.

Good:

> Interface-emulation prompts work by combining role, state, and output restriction; the failure risk is that simulated results look authoritative even when no real tool execution happened.

For risky/adversarial sources, describe the defensive lesson, not operational misuse steps.

Example:

```markdown
- **Pattern lesson:** DAN-style prompts show how dual-persona framing, fictional autonomy, and compliance pressure can be used to confuse instruction hierarchy. The defensive lesson is to reject requests that ask the model to roleplay an unconstrained version of itself or treat fictional personas as policy exceptions.
```

## Source Quality Tags

Use tags like:

- `official`
- `paper`
- `github`
- `reddit`
- `hacker-news`
- `community`
- `prompt-marketplace`
- `image-prompt`
- `coding-agent`
- `multi-agent`
- `jailbreak-history`
- `meta-prompt`
- `prompt-pack`
- `evaluation`
- `speculative`
- `hype`
- `verified-later`

## Safety Rules

- Do not store runnable jailbreak prompts.
- Do not copy paid/proprietary prompts in full.
- Do not store private user data.
- Use short excerpts and structure summaries by default.
- Mark unverified claims clearly.
- If a source is useful but risky, store it as history/defense material.
- For risky entries, `Pattern lesson` must describe the safe/defensive lesson.

## Entry Quality Check

Before adding an entry, check:

- Can someone find the original source again?
- Does the entry say how the prompt/source is built?
- Does it explain why the source matters?
- Does it include a reusable `Pattern lesson`?
- Does it avoid copying long or unsafe prompt text?
- Are tags specific enough to find it later?

If `Pattern lesson` is generic, the entry is not finished.

## Index Update Rule

After adding a new corpus batch, update:

`references/source-index.md`

Add:

- range
- file path
- main focus
- notes

If the folder needs navigation, update:

`prompt-corpus/README.md`

## Deduplication Rule

Before adding a new source, check for:

- same URL
- same repository mirror
- same Reddit thread repost
- same prompt pack under a different name
- same official doc mirrored by a blog

If duplicate, either:

- skip it
- merge notes into existing entry
- mark it as mirror/secondary source

## When To Create a New File

Create a new file when:

- a batch reaches about 20–50 entries
- the topic changes significantly
- the file is becoming hard to scan
- the entries need different safety rules

## Default Workflow

1. Decide the ID range.
2. Create or update the right corpus file.
3. Add entries with stable metadata.
4. Add a concrete `Pattern lesson` for each entry.
5. Avoid long copied prompt text.
6. Update `references/source-index.md`.
7. Update folder README if needed.
8. Report only what changed.

## User-Facing Report

Keep it short:

> 완료. PR101–PR120 추가했고, source-index도 갱신했어.

Do not dump the full table unless the user asks.
