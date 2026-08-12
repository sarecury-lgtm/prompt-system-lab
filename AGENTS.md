# PSOS repository instructions

These instructions apply to every AI agent and maintainer working in this repository.

## Read before changing anything

1. Read `PSOS_MASTER.md`.
2. Read `ACTIVE_GOAL.json`.
3. Read `governance/PSOS_CHANGE_SCOPE.json`.
4. Preserve the parent goal and the current task exactly. Do not infer a new project from the most recent example.

## Fixed parent goal

PSOS is a general problem-solving system. It should take an ordinary user request and choose the smallest sufficient combination of AI reasoning, direct answering, research, reuse, prompting, code, files, tools, verification, and limited replanning to produce the fastest high-quality usable result.

Shopping, stock analysis, candidate correction, prompt generation, and any other domain are test cases or optional tools. They are not the product goal.

## Required change classification

Before creating or editing files, classify the work as exactly one of:

- `CORE`: behavior needed across unrelated request domains.
- `ADAPTER`: a way to execute or connect the core, such as Codex, manual ChatGPT, web search, browser, or file patching.
- `DOMAIN`: a tool that applies only to a specific field or task family.
- `TEST`: experiments, fixtures, evaluations, documentation, and regression scenarios.

Do not describe a `DOMAIN` or `TEST` result as the PSOS core, the next generation of PSOS, or proof of general capability.

## Scope rules

- A short continuation such as `ㄱㄱ`, `진행`, `계속`, or `go ahead` authorizes only the already recorded current task. It does not authorize changing the parent goal, promoting an experiment, enabling a new default path, or expanding into a new domain.
- Do not connect `DOMAIN` or `TEST` work to the canonical runtime, default UI, or launcher unless the user explicitly approves that promotion and cross-domain evidence satisfies `ACTIVE_GOAL.json`.
- A feature may be called `CORE` only when its interface and behavior are domain-neutral and it has evidence across at least the required number of distinct regression domains.
- Prefer the smallest sufficient action. Adding more agents, more model calls, or more stages is not progress unless it adds new reliable information or execution capability.
- Preserve exact user constraints and source evidence. Do not replace missing context with a summary that changes decisions.
- Incomplete work must remain `partial`, `blocked`, or experimental. Do not expose it as a recommendation or completed default behavior.

## Required checks

Run the goal guard before considering the work complete:

```powershell
python -B scripts/problem_solving_goal_guard.py --base origin/main
```

Run the cross-domain governance tests and the relevant implementation tests. If the guard reports an unclassified file, scope drift, prohibited default enablement, or insufficient promotion evidence, stop and fix the classification or ask for explicit approval. Do not work around the guard.
