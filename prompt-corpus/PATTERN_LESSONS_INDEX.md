# Pattern Lessons Index

## Purpose

This is the practical entry point for using the corpus.

The corpus files preserve sources. This index extracts the reusable prompt-design moves so they can be applied when writing real prompts.

Use this file when you want to answer:

> “What pattern should I use for this prompt?”

## How To Use

1. Pick the job you are doing.
2. Find the matching pattern below.
3. Copy the reusable move into your prompt.
4. Add task-specific context, constraints, and output format.
5. Test with 2–3 realistic inputs.

## Current Pattern Lessons

| Pattern | Use when | Reusable move | Source entries | Main risk |
|---|---|---|---|---|
| Role + task frame | The prompt is vague and needs a clear work mode | `You are [role]. Your task is [objective]. Use [constraints]. Return [output shape].` | PR001 | Decorative roleplay without success criteria |
| Interface emulation | You want the model to simulate a tool or UI surface | `Return simulated [tool/interface] output only; do not claim real execution.` | PR002 | Fake execution results that look real |
| Prompt improvement loop | You want to improve a weak prompt before using it | `Diagnose missing control points → rewrite the prompt → name what changed.` | PR011 | Polished but overcomplicated prompt that drifts from the real goal |
| Defensive jailbreak analysis | You are studying adversarial prompts safely | `Classify the attack mechanism; do not reproduce runnable jailbreak text.` | PR025 | Accidentally storing or improving unsafe operational text |
| Grounded research | The answer depends on external/current sources | `Search/inspect sources → cite claims → mark unknowns → separate recommendation from evidence.` | PR064, PR076, PR106, PR109 | Confident synthesis from weak or stale sources |
| Structured output / extraction | The output must be parsed, compared, or reused | `Define fields, null policy, evidence rule, and exact output shape.` | PR061, PR062, PR064, PR106 | Pretty formatting without enforceable schema |
| Evaluation rubric | You need to judge prompt/output quality consistently | `Define criteria, scoring anchors, pass/fail rules, and failure examples.` | PR065, PR110, PR111, PR118 (testing infrastructure; needs stronger rubric-specific evidence) | Vague “quality” judgment that cannot catch regressions |
| Persistent project instruction | The prompt should control ongoing assistant behavior | `Define trigger, default behavior, boundaries, routing, and fallback.` | PR114, PR115, PR116, PR122 | Rule pile with no priority or trigger |
| Coding-agent workflow | The model works inside files, repos, tools, or code tasks | `Inspect context → make smallest safe change → validate → summarize diff.` | PR086, PR087, PR088, PR089, PR090, PR091, PR092, PR093 | Tool-using agent edits too much or skips validation |

## Pattern Details

### 1. Role + Task Frame

**Best for**

- weak prompts like “analyze this” or “make this better”
- writing, review, planning, explanation, and coaching prompts
- turning casual requests into usable instruction surfaces

**Core move**

```text
You are [practical role].
Your task is [specific objective].
Use [context and constraints].
Return [specific output shape].
```

**Why it works**

The role narrows the response style, but the task and output contract do the real control work.

**Do not overuse**

Avoid empty prestige roles like “world-class expert” unless the prompt also defines what expert behavior means.

**Related source entries**

- PR001 — Awesome ChatGPT Prompts

---

### 2. Interface Emulation

**Best for**

- mock terminal examples
- simulated console output
- teaching command/result concepts
- UI behavior sketches

**Core move**

```text
Simulate [interface].
Return only the simulated output surface.
Do not claim that commands, code, tools, or external systems actually ran.
```

**Why it works**

The prompt limits the assistant to one narrow response channel.

**Do not overuse**

Never treat simulated output as evidence. Real execution needs a real tool.

**Related source entries**

- PR002 — Act as Linux Terminal
- PR005 — Act as JavaScript Console
- PR006 — Act as Excel Sheet

---

### 3. Prompt Improvement Loop

**Best for**

- rewriting messy prompts
- turning long research prompts into compact prompts
- converting one-off prompts into project instructions or skill-lite workflows

**Core move**

```text
First diagnose what the prompt is missing.
Then rewrite it.
Then list only the important changes.
Do not add assumptions that change the user's goal.
```

**Why it works**

It makes the model inspect the instruction surface before trying to solve the task.

**Do not overuse**

Do not add heavy structure unless the task needs it. Some prompts only need one clear sentence and an output format.

**Related source entries**

- PR011 — Act as Prompt Enhancer
- PR036 — Absurdly Useful Micro-Prompts
- PR106 — Prompt for Seeking Clarity and Avoiding Hallucinating

---

### 4. Defensive Jailbreak Analysis

**Best for**

- studying unsafe prompt patterns
- building safety reviews
- identifying instruction-hierarchy attacks
- writing defensive specs

**Core move**

```text
Analyze this as a defensive prompt-safety artifact.
Do not reproduce or improve runnable jailbreak text.
Classify the mechanism: identity override, hierarchy inversion, dual-channel response, reward/punishment pressure, fake system authority, or another mechanism.
```

**Why it works**

It keeps the useful lesson while avoiding operational misuse.

**Do not overuse**

Do not let adversarial prompt study become a prompt-improvement workflow for unsafe text.

**Related source entries**

- PR025 — ChatGPT DAN Repository
- PR026 — LLM Jailbreaks
- PR027 — ChatGPT DAN Jailbreak Gist
- PR028–PR032 — DAN / anti-DAN community history

---

### 5. Grounded Research

**Best for**

- product research
- current information checks
- source-backed comparisons
- “find the best X” tasks where price, availability, policy, law, or specs may change
- any task where unsupported synthesis would be harmful

**Core move**

```text
Research [target] using source-traceable evidence.
For each important claim, include source, date checked, and confidence.
Separate confirmed facts from inference.
Mark unknowns as “확인 불가” instead of guessing.
End with a decision table or recommendation only after evidence is shown.
```

**Why it works**

Research prompts fail when they skip from search results to confident conclusion. This pattern forces evidence collection, uncertainty handling, and final judgment into separate layers.

**Do not overuse**

Do not use this heavy structure for simple explanation tasks. Use it when the answer depends on changing facts or source quality.

**Related source entries**

- PR064 — OpenAI Prompt Examples / Cookbook
- PR076 — LangChain Hub Prompts
- PR106 — Anti-hallucination / clarity prompt
- PR109 — RAG / hallucination-control claim

---

### 6. Structured Output / Extraction

**Best for**

- extracting fields from documents
- turning messy text into JSON, tables, or checklists
- classification tasks
- comparison tables
- workflows where another tool or human will reuse the output

**Core move**

```text
Extract only the requested fields.
Use this exact output shape: [schema/table/fields].
If a value is missing, return null or an empty list.
Include evidence text when the task depends on source grounding.
Output no extra commentary unless requested.
```

**Why it works**

The model has less room to invent structure when fields, missing-value policy, and evidence rules are fixed. This also makes downstream review easier.

**Do not overuse**

Do not force strict JSON when the user needs judgment, nuance, or explanation. Use structured output where consistency matters more than prose quality.

**Related source entries**

- PR061 — Anthropic Prompt Library
- PR062 — OpenAI Cookbook
- PR064 — Learn Prompting
- PR106 — Prompt for Seeking Clarity and Avoiding Hallucinating

---

### 7. Evaluation Rubric

**Best for**

- judging prompt quality
- comparing two prompts or two outputs
- checking whether a skill is working
- reviewing model answers consistently across examples
- building manual specs before automation exists

**Core move**

```text
Evaluate [artifact] against these criteria:
1. [criterion]
2. [criterion]
3. [criterion]

For each criterion, use anchors:
- pass: [observable behavior]
- partial: [borderline behavior]
- fail: [failure behavior]

Return verdict, strongest part, weakest part, and one next edit.
```

**Why it works**

Rubrics turn vague taste into repeatable judgment. Anchors matter more than scores because they tell the reviewer what concrete behavior counts as success or failure.

**Do not overuse**

Do not create a giant scoring grid when the decision only needs one clear weakness and one fix.

**Related source entries**

- PR065 — OpenAI Evals Prompting Examples
- PR110 — Prompt evaluation discussion
- PR111 — Prompt evaluator meta-prompt
- PR118 — Prompt testing tools discussion (testing infrastructure; needs stronger rubric-specific evidence)

---

### 8. Persistent Project Instruction

**Best for**

- ChatGPT Projects
- Custom GPT instructions
- Claude Project instructions
- assistant-wide behavior rules
- recurring user preferences
- repo-level Codex operating instructions

**Core move**

```text
# Purpose
This instruction applies when [trigger/context].

# Behavior
- Prioritize [priority].
- Do [default behavior].
- Avoid [bad behavior].

# Routing
- If input is [type A], do [workflow A].
- If input is [type B], do [workflow B].

# Output
Return [fields/style].

# Boundaries
If information is missing, [fallback].
```

**Why it works**

Persistent instructions need triggers and priority more than one-off prompts do. Without them, they become a pile of preferences that may not activate at the right time.

**Do not overuse**

Do not put temporary task requirements into project instructions. Keep persistent rules stable and reusable.

**Related source entries**

- PR114 — ChatGPT Project instruction discussion
- PR115 — Project instruction workflow discussion
- PR116 — Custom instruction / project instruction discussion
- PR122 — System-prompt archive metadata

---

### 9. Coding-Agent Workflow

**Best for**

- repo editing
- file refactoring
- debugging
- PR creation
- Codex-style tasks
- tool-using assistant workflows

**Core move**

```text
Inspect the relevant files first.
Make the smallest safe change that solves the task.
Do not make unrelated refactors.
Run tests or checks if available.
If tests are unavailable, say what was checked instead.
Summarize changed files and next action.
Ask before destructive changes.
```

**Why it works**

Coding agents fail by editing too much, skipping context, or claiming validation they did not run. This pattern constrains scope and forces a verifiable end state.

**Do not overuse**

Do not use a full repo-agent workflow for simple code snippets. Use it when files, tools, or project state matter.

**Related source entries**

- PR086 — Cursor Rules / `.cursorrules` Pattern
- PR087 — Cursor Directory Rules
- PR088 — Cline System Prompt Lineage
- PR089 — Roo Code / Roo-Code Agent Prompts
- PR090 — Open Interpreter System Prompt Lineage
- PR091 — Aider Coding Prompts
- PR092 — Continue.dev Prompt Templates
- PR093 — GPT Engineer Prompt Lineage

## Quick Selection Guide

| User need | Start with |
|---|---|
| “프롬프트가 너무 애매해” | Role + task frame |
| “이걸 실제 도구처럼 흉내내고 싶어” | Interface emulation |
| “내 프롬프트를 개선하고 싶어” | Prompt improvement loop |
| “DAN/탈옥류 구조를 분석하고 싶어” | Defensive jailbreak analysis |
| “웹에서 조사해서 근거 있게 찾아줘” | Grounded research |
| “문서에서 정보 뽑아서 표/JSON으로 정리해줘” | Structured output / extraction |
| “이 프롬프트/답변이 좋은지 평가해줘” | Evaluation rubric |
| “이걸 프로젝트 지침으로 넣고 싶어” | Persistent project instruction |
| “repo 파일 수정/코드 작업을 시키고 싶어” | Coding-agent workflow |

## Next Patterns To Add

Add only after the current patterns have been used in real examples:

- prompt registry/versioning pattern
- image-prompt anatomy pattern
- multi-agent role-and-handoff pattern
- prompt compression / micro-prompt pattern
- source excerpt pattern for corpus entries
