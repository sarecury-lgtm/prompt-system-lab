# Personal Prompt Quality System

This plan adds a verified-prompt track to the existing prompt-system lab. It does not replace the current corpus, skills, specs, or pattern-verification work.

## Purpose

Build a higher-trust pipeline for learning from prompts:

1. Verified prompt collection
2. Prompt decomposition
3. Pattern extraction
4. Reusable workflow updates

The key difference from a broad prompt corpus is evidence quality. A prompt should not become a reusable lesson until its source, context, and limitations are understood.

## Track Structure

### 1. Collect Verified Prompts

Start with `tasks/task-000-collect-verified-prompts.md`.

A verified prompt candidate should have:

- Traceable source evidence
- Clear task context
- Known author, publisher, product, or project when possible
- Enough surrounding explanation to understand intended use
- Safe excerpting or summarization boundaries

### 2. Decompose Prompt Mechanics

For each accepted prompt, identify:

- Role or stance
- Task framing
- Input assumptions
- Output contract
- Constraints and refusal boundaries
- Examples or rubrics
- Verification behavior
- Known failure modes

### 3. Extract Patterns

Promote a mechanism into a reusable pattern only when it is supported by source evidence and can be described without copying long prompt text.

Useful pattern notes should explain:

- What the pattern does
- Why it works
- When it fails
- What tasks it fits
- How to reuse it safely

### 4. Connect Back To Existing Repo

This track should feed the existing system instead of replacing it:

- `prompt-corpus/` remains the source-traceable corpus area.
- `prompt-corpus/PATTERN_VERIFICATION.md` remains the verification reference.
- `skills/` remains the reusable workflow layer.
- `specs/` remains the manual behavior-check layer.

## Operating Principle

Treat prompt quality as an evidence problem. A prompt can look polished and still be weak, fake, overfit, copied without context, or unsafe to reuse. The track should preserve that uncertainty until verification supports a pattern claim.
