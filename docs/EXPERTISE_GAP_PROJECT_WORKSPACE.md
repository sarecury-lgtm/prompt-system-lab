# Expertise-Gap Project Workspace Template

Use this template for long-running projects where the user may not know the established expert solution space yet. The goal is not to store every conversation. It is to preserve the minimum state needed to reconstruct what is true, what has been tried, why the current direction exists, and what should be tested next.

## Suggested workspace

```text
project/
├── 00_START_HERE.md
├── STATE.md
├── PROBLEM_MAP.md
├── BENCHMARK.md
├── ERROR_TAXONOMY.md
├── DECISIONS.md
├── EXPERIMENTS.md
├── OPEN_QUESTIONS.md
└── EVIDENCE/
```

## 00_START_HERE.md

Keep this short.

```md
# Project

## Goal
What real outcome are we trying to achieve?

## Current decision
What are we deciding or building now?

## Success criteria
What observable result would count as success?

## Read order
1. STATE.md
2. PROBLEM_MAP.md
3. BENCHMARK.md
4. ERROR_TAXONOMY.md
5. DECISIONS.md
6. EXPERIMENTS.md
7. OPEN_QUESTIONS.md
```

## STATE.md

Record only the current state, not the full history.

```md
# Current State

## Current architecture / approach

## What works

## Largest observed bottlenecks

## Current assumptions

## Current uncertainties

## Next planned action
```

## PROBLEM_MAP.md

Capture the expert map of the problem so the project is not bounded by the user's first ideas.

```md
# Problem Map

| Subproblem | Established name / field | Baseline | Strong current approaches | Known limits | Relevance to our data |
|---|---|---|---|---|---|
```

Update this when research changes the shape of the problem, not whenever a new paper appears.

## BENCHMARK.md

Use a small representative benchmark before large implementation commitments.

```md
# Benchmark

## Representative sample
What data is included and why is it representative?

## Ground truth
How was it created and what uncertainty remains?

## Metrics
Which metrics correspond to the real user outcome?

## Baseline results
| Version | Metric | Result | Notes |
|---|---|---|---|
```

## ERROR_TAXONOMY.md

Track where the system actually fails.

```md
# Error Taxonomy

| Error type | Frequency | Impact | Current cause hypothesis | Candidate remedies | Evidence |
|---|---:|---:|---|---|---|
```

When possible, prioritize using a combination of frequency, impact, solvability, and implementation cost rather than novelty.

## DECISIONS.md

Keep a decision log instead of relying on conversational memory.

```md
# Decisions

## DEC-001 — <decision>
Status: active / superseded / reversed
Date:

Decision:

Why:

Evidence:

Unknowns:

Alternatives considered:

Revisit if:

Reusable assets if reversed:
```

A decision is not permanent. It should be easy to overturn when its evidence changes.

## EXPERIMENTS.md

Use experiments to remove uncertainty, not merely to generate activity.

```md
# Experiments

## EXP-001 — <question>
Hypothesis:

Decision this experiment can change:

Minimum test:

Success criterion:

Failure criterion:

Result:

Interpretation:

Decision impact:
```

Prefer the cheapest experiment that discriminates between leading hypotheses.

## OPEN_QUESTIONS.md

Keep only questions whose answers can change architecture, ranking, or next action.

```md
# Open Questions

| Question | Why it matters | What decision it can change | Cheapest way to answer | Priority |
|---|---|---|---|---|
```

If a question is merely interesting, do not let it compete with decision-changing unknowns.

## EVIDENCE/

Store source notes, research reports, benchmark references, model cards, or other evidence needed to reconstruct important claims. Avoid turning this directory into an uncurated archive.

## Review modes

### Local improvement review

Use when the parent architecture is still well supported.

Ask:

- What is the largest current error or bottleneck?
- Is development effort proportional to its real impact?
- What is the smallest change or experiment that could improve it?

### Clean-slate review

Use after several material experiments, before a costly architectural commitment, after a major external technology change, or when progress feels locally optimized but directionally uncertain.

Ask:

- If we had today's evidence but no sunk cost, would we choose the same architecture?
- Which current components survive because they are useful, and which survive only because we already built them?
- Are we re-solving a problem for which a stronger established solution already exists?
- What important expert baseline, benchmark, implementation, or failure mode are we missing?
- What single experiment would most reduce uncertainty about the next architecture decision?

## Suggested project audit prompt

```text
Review this workspace as an independent technical lead. Treat current decisions as hypotheses, not truths.

Use the project evidence and current state to determine:
1. the largest real bottlenecks,
2. whether development effort matches their impact,
3. whether established baselines or strong current implementations are being missed,
4. where complexity has been added without sufficient evidence,
5. whether you would choose the same architecture from scratch today,
6. what should be removed, added, or repositioned if not,
7. the cheapest next experiment that can change the decision.

Preserve reusable work, but do not preserve weak architecture because of sunk cost. Distinguish observed facts, supported conclusions, and open hypotheses.
```
