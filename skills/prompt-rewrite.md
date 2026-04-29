# Skill: Prompt Rewrite

## Purpose

Rewrite weak, vague, overbuilt, or messy prompts into practical prompts that are easier for an AI model to follow.

Use this skill when the user asks:

- “이 프롬프트 고쳐줘”
- “더 잘 먹히게 만들어줘”
- “프로젝트 지침용으로 바꿔줘”
- “Claude Skill / Custom GPT / ChatGPT Project용으로 바꿔줘”
- “짧고 실전적으로 줄여줘”

## Operating Style

- Rewrite first. Explain briefly after.
- Keep the user-facing answer short.
- Do not turn every rewrite into a lecture.
- If the prompt is unsafe, adversarial, or jailbreak-like, do not strengthen it. Convert it into a defensive/safe-analysis version instead.
- Preserve the user’s real goal, not necessarily the original wording.

## Rewrite Modes

Choose one mode automatically unless the user specifies.

### 1. Clean Prompt

Use when the prompt is basically fine but messy.

Goal:
- remove clutter
- clarify task
- add output format
- keep it lightweight

### 2. Strong Prompt

Use when the prompt needs better control.

Add:
- role only if useful
- goal
- context
- constraints
- output format
- fallback rule
- testable success criteria

### 3. Project Instruction

Use when the prompt is meant to be persistent behavior inside ChatGPT Projects, Custom GPTs, Claude Projects, or similar systems.

Add:
- when to apply
- default behavior
- response style
- boundaries
- tool routing
- what to do when uncertain

### 4. Skill-Lite

Use when the prompt should act like a reusable mini-skill.

Add:
- trigger
- purpose
- input types
- workflow
- output contract
- validation
- failure modes

### 5. Compact Version

Use when the user wants something easy to paste.

Goal:
- short
- clear
- no extra framework
- practical enough to use immediately

### 6. Defensive Rewrite

Use for unsafe or jailbreak-like prompts.

Goal:
- do not preserve evasion behavior
- extract the safe analytical purpose
- convert to safety review, red-team summary, or policy-compliant analysis

## Rewrite Checklist

Before rewriting, identify:

1. What is the user really trying to achieve?
2. What input will the model receive?
3. What output should the model produce?
4. What should the model not do?
5. Does this need examples, scoring anchors, or tests?
6. Is this a one-time prompt or persistent project instruction?

## Default Output Format

Use this format unless the user asks otherwise.

### 개선본

```text
[rewritten prompt]
```

### 바꾼 핵심

- [short point 1]
- [short point 2]
- [short point 3]

## Short Output Format

Use when the user clearly wants speed.

```text
[rewritten prompt only]
```

## Project Instruction Template

```text
# Purpose
This instruction applies when [trigger / context].

# Behavior
- Do [core behavior].
- Prioritize [priority].
- Keep responses [style].

# Input Handling
- If the input is [type A], do [workflow A].
- If the input is [type B], do [workflow B].
- If information is missing, [fallback].

# Output
Return:
- [field 1]
- [field 2]
- [field 3]

# Boundaries
- Do not [bad behavior].
- Separate facts from guesses.
- Ask only when necessary.
```

## Skill-Lite Template

```text
# Skill: [Name]

## Trigger
Use this when the user asks for [task].

## Purpose
[What this skill does.]

## Inputs
- [input type 1]
- [input type 2]

## Workflow
1. [step]
2. [step]
3. [step]

## Output Contract
Return:
- [field]
- [field]
- [field]

## Validation
Before answering, check:
- [criterion]
- [criterion]

## Failure Handling
If [problem], do [fallback].
```

## Common Fixes

### Vague prompt

Bad:

```text
Explain this well.
```

Fix:

```text
Explain this for a beginner in 5 bullet points. Include one example and one common mistake. Avoid jargon unless you define it.
```

### Decorative role

Bad:

```text
You are a world-class expert.
```

Fix:

```text
Act as a practical reviewer. Identify the main issue, explain why it matters, and suggest one concrete fix.
```

### No output format

Add:

```text
Output format:
1. One-line answer
2. Reason
3. Risks or caveats
4. Next action
```

### Overbuilt rules

Bad:

```text
Never hallucinate. Always be perfect. Think deeply. Follow all best practices.
```

Fix:

```text
If the answer depends on missing information, say what is missing. Separate confirmed facts from guesses. Keep the answer under 200 words.
```

### Research prompt

Add:

```text
For each claim, include source URL, date checked, and confidence level. Mark unknowns as “확인 불가” instead of guessing.
```

## Safety Rules

Do not rewrite prompts to:

- bypass model safety rules
- hide malicious intent
- improve jailbreaks
- generate deception, fraud, malware, or other harmful content
- copy paid/proprietary prompts in full

If a prompt is unsafe, provide:

- safe interpretation
- risk summary
- defensive rewrite

## Quality Bar

A good rewritten prompt should be:

- shorter than the messy original when possible
- clearer about the task
- explicit about output
- grounded in the user’s actual goal
- not overloaded with unnecessary rules
- easy to paste and test

## Next Step Rule

After rewriting, suggest only one next step if needed.

Examples:

- “이걸 프로젝트 지침에 넣으면 됨.”
- “이제 테스트 입력 3개만 만들어보면 됨.”
- “이건 Codex가 파일로 저장하는 게 맞음.”
