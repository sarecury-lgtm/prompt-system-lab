# Skill: Prompt Design Workflow

## Purpose

Turn a rough user goal into a usable prompt without overbuilding it.

Use this when the user asks:

- “프롬프트 짜줘”
- “이걸 어떻게 시키면 좋을까?”
- “심층 리서치용 프롬프트 만들어줘”
- “프로젝트 지침으로 바꿔줘”
- “Claude/ChatGPT/Codex에 넣을 지침 만들어줘”

## Operating Style

- Build the usable prompt first.
- Explain only the important choices after.
- Do not dump long theory unless asked.
- Prefer compact prompts over heavy frameworks.
- Add structure only when it improves control, testing, or reuse.
- Do not claim corpus grounding unless a specific pattern or source entry shaped the output.

## Corpus-First Rule

Before writing a prompt, use `prompt-corpus/PATTERN_LESSONS_INDEX.md` as the pattern map.

For every prompt-design request, internally check:

1. Which pattern lesson best matches the request?
2. Which reusable move from that pattern should shape the prompt?
3. Which related source entries are relevant enough to inspect if more detail is needed?
4. Which tempting pattern should not be used because it would overbuild the prompt?

Do not output a generic prompt if a more specific pattern applies.

The user-facing answer does not need to show this reasoning every time. When useful, include a short note under `적용한 패턴`.

## Fast Workflow

1. Identify the real job.
2. Decide whether it is a one-time prompt, project instruction, reusable skill, repo-agent task, extraction task, research task, or evaluation task.
3. Choose the smallest useful pattern from `prompt-corpus/PATTERN_LESSONS_INDEX.md`.
4. Apply that pattern’s reusable move.
5. Write the prompt.
6. Add output format.
7. Add one failure/fallback rule.
8. Give one next test input if useful.

## Pattern Selection

Use `prompt-corpus/PATTERN_LESSONS_INDEX.md` as the first pattern map.

### If the request is vague

Use role + task frame.

```text
You are [role].
Your task is [objective].
Use [context].
Return [output format].
```

### If the request needs source-grounded research

Use grounded research.

```text
Research [target] using source-traceable evidence.
For each important claim, include source, date checked, and confidence.
Separate confirmed facts from inference.
Mark unknowns as “확인 불가” instead of guessing.
End with a decision table or recommendation only after evidence is shown.
```

### If the request needs structured extraction or reusable output

Use structured output / extraction.

```text
Extract only the requested fields.
Use this exact output shape: [schema/table/fields].
If a value is missing, return null or an empty list.
Include evidence text when the task depends on source grounding.
Output no extra commentary unless requested.
```

### If the request asks for review, scoring, or comparison

Use evaluation rubric.

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

### If the request needs prompt improvement

Use prompt improvement loop.

```text
Diagnose the prompt's missing control points.
Rewrite it for the user's real goal.
List only the changes that matter.
Avoid adding assumptions.
```

### If the request is for persistent behavior

Use persistent project instruction.

```text
# Purpose
This applies when [trigger].

# Behavior
- Do [core behavior].
- Prioritize [priority].
- Keep responses [style].

# Routing
- If input is [type A], do [workflow A].
- If input is [type B], do [workflow B].

# Output
Return [fields].

# Boundaries
- Do not [bad behavior].
- If information is missing, [fallback].
```

### If the request should become a reusable mini-skill

Use skill-lite mode, usually combining persistent project instruction with a workflow and validation block.

```text
# Skill: [Name]

## Trigger
Use when [situation].

## Workflow
1. [step]
2. [step]
3. [step]

## Output Contract
Return:
- [field]
- [field]

## Validation
Check [criteria] before answering.
```

### If the request involves repo/file/code agent work

Use coding-agent workflow.

```text
Inspect the relevant files first.
Make the smallest safe change that solves the task.
Do not make unrelated refactors.
Run tests or checks if available.
If tests are unavailable, say what was checked instead.
Summarize changed files and next action.
Ask before destructive changes.
```

## Pattern Trace Note

When the user asks why the prompt is structured that way, or when the prompt is complex, include this compact note after the prompt:

```markdown
### 적용한 패턴

- Pattern: [name from PATTERN_LESSONS_INDEX.md]
- Reusable move: [the move used]
- Not used: [one tempting but unnecessary pattern] — [short reason]
```

Do not include this note when the user clearly wants only the final prompt.

## Default User-Facing Output

Use this unless the user asks for a file or repo edit.

```markdown
### 바로 쓸 프롬프트

```text
[prompt]
```

### 핵심만

- [why this structure]
- [what to test next]
```

For complex prompt-design tasks, optionally add:

```markdown
### 적용한 패턴

- Pattern: [pattern]
- Reusable move: [move]
```

## When Editing The Repo

If working inside this repository:

- add reusable prompt workflows to `skills/`
- add source-derived patterns to `prompt-corpus/PATTERN_LESSONS_INDEX.md`
- add raw source entries to `prompt-corpus/`
- update `references/source-index.md` only when adding/changing corpus batches
- update `README.md` only when navigation or status changes

## Quality Bar

A usable prompt should answer:

- What is the model supposed to do?
- Which corpus pattern shaped the prompt?
- What input will it receive?
- What should the output look like?
- What should it not invent?
- What should happen when information is missing?

If those are unclear, the prompt is not ready.

## Avoid

- long motivational intros
- fake expertise labels without task criteria
- ten-step workflows for simple tasks
- “always/never/perfect” rules that cannot be tested
- explanation dumps before the actual prompt
- saying the corpus was used when no pattern or reusable move actually changed the output

## One-Minute Test

Before considering a prompt done, run this mental test:

> If a different AI saw only this prompt and one realistic input, would it know what to produce, what not to invent, and which pattern it follows?

If no, add only the missing control point.
