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

## Fast Workflow

1. Identify the real job.
2. Decide whether it is a one-time prompt, project instruction, or reusable skill.
3. Choose the smallest useful pattern.
4. Write the prompt.
5. Add output format.
6. Add one failure/fallback rule.
7. Give one next test input if useful.

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

Use grounded research frame.

```text
Research [target].
Prioritize primary/current sources.
For each important claim, include source, date checked, and confidence.
Mark unknowns as 확인 불가 instead of guessing.
End with a short recommendation or decision table.
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

Use project instruction mode.

```text
# Purpose
This applies when [trigger].

# Behavior
- Do [core behavior].
- Prioritize [priority].
- Keep responses [style].

# Output
Return [fields].

# Boundaries
- Do not [bad behavior].
- If information is missing, [fallback].
```

### If the request should become a reusable mini-skill

Use skill-lite mode.

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

## One-Minute Test

Before considering a prompt done, run this mental test:

> If a different AI saw only this prompt and one realistic input, would it know what to produce and what not to invent?

If no, add only the missing control point.
