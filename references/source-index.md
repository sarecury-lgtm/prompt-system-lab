# Source Index

## Purpose

Maintain a compact map of the sources and corpus files used in this project.

This file is not the full corpus. It is the navigation index for finding where each batch lives.

## Prompt Corpus Files

| Range | File | Main focus | Notes |
|---|---|---|---|
| PR001–PR020 | `prompt-corpus/famous-prompts.md` | Early famous ChatGPT prompt collections and “Act as…” role prompts | First seed batch. Includes prompts.chat, translator, interviewer, terminal, JavaScript console, travel guide, advertiser, storyteller, prompt enhancer, and early GitHub prompt collections. |
| PR021–PR040 | `prompt-corpus/famous-prompts-pr021-pr040.md` | Programming prompts, academic prompts, jailbreak-history sources, Reddit popular prompt lists, OpenAI student prompt sources | Includes coding prompt packs, academic writing prompts, DAN/jailbreak history as metadata-only, Reddit popular prompt threads, and student-use prompt packs. |
| PR041–PR060 | `prompt-corpus/famous-prompts-pr041-pr060.md` | Official prompt packs, media prompt roundups, FlowGPT, OpenAI Community prompt threads, image prompt guides | Includes OpenAI Academy, Tom’s Guide, Medium prompt lists, FlowGPT, OpenAI Cookbook, OpenAI Community threads, and educational prompt PDFs. |
| PR061–PR080 | `prompt-corpus/famous-prompts-pr061-pr080.md` | Official prompt libraries, prompt marketplaces, image prompt ecosystems, agent/template frameworks | Includes Anthropic, OpenAI Cookbook, Learn Prompting, DAIR, PromptHero, PromptBase, AIPRM, AutoGPT, BabyAGI, Semantic Kernel, LangChain, Midjourney, OpenArt, Lexica. |
| PR081–PR100 | `prompt-corpus/famous-prompts-pr081-pr100.md` | Fabric patterns, Cursor rules, coding-agent prompts, multi-agent frameworks, prompt indexes | Includes Fabric, Cursor rules, Cline, Roo Code, Open Interpreter, Aider, Continue, GPT Engineer, ChatDev, MetaGPT, AutoGen, CrewAI, SuperAGI, CAMEL, GitHub prompt topic indexes. |

## Skill Files

| Skill | File | Purpose |
|---|---|---|
| Prompt Analysis | `skills/prompt-analysis.md` | Analyze prompt quality, structure, risks, and improvement opportunities. |
| Prompt Rewrite | `skills/prompt-rewrite.md` | Rewrite weak or messy prompts into clean, strong, project-instruction, or skill-lite versions. |
| Corpus Indexing | `skills/corpus-indexing.md` | Manage ID rules, batch files, tags, deduplication, and index updates. |
| Source Collection | `skills/source-collection.md` | Collect famous, controversial, official, GitHub, Reddit, paper, marketplace, and agent-prompt sources in a traceable way. |

## Test Files

| Test file | Purpose |
|---|---|
| `tests/prompt-analysis-tests.md` | Manual test cases for prompt analysis behavior. |
| `tests/prompt-rewrite-tests.md` | Manual test cases for prompt rewrite behavior. |

## Source Families

| Family | Examples | Why it matters |
|---|---|---|
| Early ChatGPT role prompts | prompts.chat, “Act as…” prompts | Shows the first mainstream prompt-sharing style: role assignment, behavior framing, and output constraints. |
| Meta-prompts | Prompt Enhancer, Anthropic Prompt Generator, FlowGPT frameworks | Useful for building prompts that improve or generate other prompts. |
| Reddit / community prompts | popular prompt lists, DAN history, prompt-sharing threads | Captures what spread socially, what became controversial, and what users actually tried. |
| Official guides | OpenAI Cookbook, Anthropic Docs, OpenAI Academy | Baseline sources with safer and more current prompting patterns. |
| Prompt marketplaces | FlowGPT, PromptBase, AIPRM, PromptHero, Snack Prompt | Shows how prompts are packaged, titled, categorized, and sold/shared. |
| Image prompt ecosystems | Midjourney docs, OpenArt promptbook, Lexica, PromptHero | Useful for studying visual prompt grammar, style tags, negative prompts, and composition terms. |
| Coding-agent prompts | Cursor rules, Cline, Roo Code, Aider, Open Interpreter | Shows prompts as project rules, tool instructions, and repo-aware workflows. |
| Multi-agent prompts | AutoGPT, BabyAGI, ChatDev, MetaGPT, AutoGen, CrewAI, CAMEL | Shows prompt design moving from single-turn text to roles, tasks, tools, and process orchestration. |
| Prompt pattern libraries | Fabric, DAIR Prompting Guide, Learn Prompting | Good for reusable prompt structures and named task patterns. |

## Corpus Rules

- Keep long prompt text out unless it is safe and necessary.
- Prefer source URL, short excerpt, structure summary, tags, and safety note.
- Jailbreak prompts should stay as history/structure notes only, not runnable instructions.
- Paid or copyrighted prompts should be summarized, not copied.
- When adding a new batch, create a new file by range, then update this index.

## Current Status

- Famous prompt corpus seed: PR001–PR100 complete.
- Core skills created: prompt analysis, prompt rewrite, corpus indexing, source collection.
- Manual tests created: prompt analysis and prompt rewrite.
- Next likely batch: PR101–PR150 or separate specialized files for Reddit prompt threads, GitHub prompt packs, image prompts, and coding-agent prompts.
