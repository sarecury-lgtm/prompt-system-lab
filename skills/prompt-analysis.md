# Skill: Prompt Analysis

## Purpose

Analyze prompts, project instructions, custom GPT instructions, Claude Skills, coding-agent instructions, and prompt-library entries as reusable systems rather than isolated text.

Use this skill when the user asks to inspect, improve, compare, classify, or adapt a prompt.

## Operating Style

- Give the result first.
- Keep the explanation short unless the user asks for details.
- Do not dump the full process by default.
- When useful, reference the prompt corpus files in `prompt-corpus/` and the index in `references/source-index.md`.
- Separate what is visible in the prompt from what is inferred.

## Core Questions

When analyzing a prompt, check these points:

1. **Trigger** — When should this prompt be used?
2. **Goal** — What is the actual task?
3. **Input** — What kind of input does it expect?
4. **Role** — Does it assign a useful role, or just decorative persona?
5. **Context** — What background information is provided?
6. **Routing** — Does it handle different input types or cases?
7. **Criteria** — What standards decide good vs bad output?
8. **Output Contract** — Does it specify structure, format, length, tone, or fields?
9. **Boundaries** — What should the model avoid doing?
10. **Validation** — Is there a self-check, test case, citation rule, or review loop?
11. **Portability** — Can it be reused in ChatGPT project instructions, Custom GPT, Claude Skill, or Codex-style repo workflows?

## Fast Analysis Output

Use this when the user wants a quick answer.

### Verdict
One short judgment: good / decent / weak / overbuilt / risky.

### Why
2–4 short bullets.

### Best part
The strongest design choice.

### Weak point
The main failure risk.

### Better version
A compact improved version or next edit.

## Full Analysis Output

Use this only when the user asks for a deep breakdown.

### 1. What this prompt is trying to do
Explain the real job of the prompt.

### 2. Structure map
| Part | Present? | Notes |
|---|---:|---|
| Trigger |  |  |
| Goal |  |  |
| Role |  |  |
| Context |  |  |
| Routing |  |  |
| Criteria |  |  |
| Output Contract |  |  |
| Boundary |  |  |
| Validation |  |  |

### 3. Pattern match
Compare it to known prompt patterns from the corpus, such as:

- Act-as role prompt
- Tool simulation prompt
- Meta-prompt / prompt enhancer
- Research prompt
- Evaluation rubric prompt
- Agent/workflow prompt
- Project instruction / persistent rule prompt
- Coding-agent instruction
- Image prompt template
- Jailbreak-history / adversarial prompt pattern

### 4. Quality judgment
Score only when useful.

| Dimension | Score | Meaning |
|---|---:|---|
| Clarity | /10 | Is the task understandable? |
| Specificity | /10 | Are constraints and inputs concrete? |
| Output Control | /10 | Is the answer format stable? |
| Safety / Risk Control | /10 | Does it avoid overreach or unsafe behavior? |
| Reusability | /10 | Can it be reused across tasks? |

### 5. Rewrite
Give a revised version if the prompt is worth improving.

### 6. Test cases
Add 2–3 test inputs if the prompt needs validation.

## Red Flags

Mark these clearly:

- Vague role: “You are an expert” with no task criteria.
- Too many rules with no priority order.
- Conflicting instructions.
- Output format missing.
- No boundary between facts and guesses.
- Requests long hidden reasoning or unverifiable claims.
- Persona-heavy but task-light prompt.
- Jailbreak or policy-evasion structure.
- Paid/proprietary prompt copied without permission.
- Claims of “10x better” or “never hallucinate” without tests.

## Improvement Moves

Use these fixes:

- Add a trigger: “Use this when…”
- Add input assumptions.
- Replace decorative role with task-specific role.
- Add output fields.
- Add criteria or scoring anchors.
- Add boundary rules.
- Add a small self-check.
- Add 2–3 test cases.
- Split a giant prompt into smaller modules.
- Move reference material into corpus/reference files instead of stuffing it into one prompt.

## Default Response Style

For this user, keep the answer practical and short.

Good:

> 이건 구조는 괜찮은데 출력 기준이 약함. `판단 기준`이랑 `검수 루프`만 넣으면 훨씬 안정적임.

Bad:

> 이 프롬프트는 크게 열한 가지 관점에서 분석할 수 있으며, 첫째...

## Next Step Rule

When the analysis suggests a repo/file change, say which tool should handle it:

- **ChatGPT**: thinking, judging, rewriting, planning.
- **Codex / GitHub task**: creating files, updating corpus, adding indexes, refactoring repo structure.
