# Skill: Source Collection

## Purpose

Collect prompt-related sources in a way that is broad, source-traceable, and useful for later analysis.

Use this skill when gathering:

- famous prompts
- popular prompt packs
- Reddit / Hacker News discussion threads
- GitHub prompt repositories
- official prompt guides
- papers and surveys
- prompt marketplaces
- image-prompt sources
- coding-agent/system-prompt sources
- Claude Skills / Cursor rules / Custom GPT instructions

## Operating Style

- Collect first, analyze later.
- Prefer real source material over abstract advice.
- Prioritize famous, controversial, widely discussed, highly starred, heavily commented, or historically important sources.
- Keep the user-facing report short.
- If the assistant can update the repo directly, do it directly.
- Preserve enough metadata so the source can be found again.

## Collection Priority

Use this priority order:

1. Actual prompt text, prompt pack, prompt repository, or prompt marketplace entry.
2. Famous or controversial community thread about a prompt.
3. Official prompt pack or vendor guide with examples.
4. GitHub repo containing prompt templates, system prompts, agent prompts, or rules.
5. Paper/survey with named prompt techniques and examples.
6. Blog/media roundup only if it points to popular prompts or reflects mainstream usage.

## Source Signals

A source is worth collecting when it has one or more of these signals:

- many stars, forks, comments, upvotes, or reposts
- appears in multiple prompt lists
- historically important, such as early ChatGPT role prompts or DAN history
- official source from OpenAI, Anthropic, Microsoft, Google, Midjourney, LangChain, etc.
- large prompt library or marketplace
- unusual structure worth studying
- controversy, backlash, or strong community debate
- useful failure case

## Entry Metadata

For each source, store:

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

Optional when useful:

- fame signal
- controversy signal
- source quality
- mirror/duplicate note
- date checked

## Search Tracks

Use separate tracks instead of mixing everything:

### Prompt Corpus

Actual prompt examples and prompt collections.

ID: `PR###`

### Community Debate

Reddit, Hacker News, forum threads, controversy, prompt-is-dead debates, jailbreak debates.

ID: `C###`

### GitHub / Tools / Skills

Prompt tools, prompt packs, Claude Skills, Cursor rules, coding-agent prompts, system-prompt repos.

ID: `G###`

### Papers

Surveys, prompt technique papers, CoT/ReAct/ToT/Self-Consistency/etc.

ID: `P###`

### Official Docs

Vendor docs, official prompt libraries, prompt guides, safety/system-message docs.

ID: `O###`

## Collection Workflow

1. Pick a track.
2. Search broadly.
3. Prefer source-traceable pages.
4. Add only sources with a clear reason.
5. Store metadata, not full copied text.
6. Split into range files when needed.
7. Update `references/source-index.md`.
8. Report only the result.

## Safety Rules

- Do not reproduce runnable jailbreak prompts.
- Do not copy paid prompts in full.
- Do not copy long copyrighted prompt text.
- Do not store private user data.
- For risky sources, keep only structure and defensive notes.
- Mark unverified claims as unverified.

## Deduplication

Before adding, check whether the source is:

- same URL already collected
- same GitHub repo mirror
- same Reddit repost
- same prompt pack under a different title
- secondary article about an already collected official source

If duplicate, either skip it or add a short mirror note.

## User-Facing Report

Good:

> 완료. Reddit/GitHub prompt source PR101–PR120 추가했고 source-index 갱신했어.

Bad:

> I searched through many sources and then carefully evaluated each based on...

## Next Step Rule

After a source batch is added, choose the next obvious action:

- update source index
- update README
- create test cases
- create analysis summary
- continue next batch

Do not ask the user unless the action needs their account/UI permission.
