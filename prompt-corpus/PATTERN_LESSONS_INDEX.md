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

---

### 4. Defensive Jailbreak Analysis

**Best for**

- studying unsafe prompt patterns
- building safety reviews
- identifying instruction-hierarchy attacks
- writing defensive test cases

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

## Quick Selection Guide

| User need | Start with |
|---|---|
| “프롬프트가 너무 애매해” | Role + task frame |
| “이걸 실제 도구처럼 흉내내고 싶어” | Interface emulation |
| “내 프롬프트를 개선하고 싶어” | Prompt improvement loop |
| “DAN/탈옥류 구조를 분석하고 싶어” | Defensive jailbreak analysis |

## Next Patterns To Add

Upgrade representative entries from the remaining corpus families, then add them here:

- official docs pattern
- evaluation/rubric pattern
- RAG/grounded-answer pattern
- coding-agent project rules pattern
- prompt registry/versioning pattern
- image-prompt anatomy pattern
- multi-agent role-and-handoff pattern
