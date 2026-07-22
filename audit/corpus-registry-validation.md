# Corpus Registry Validation — 2026-07-22

## Result

Manual repository inspection passed the range-level inventory check.

- Expected corpus entries: 130
- Registry rows: 130
- Range files: 7
- Missing expected IDs observed: none
- Out-of-range IDs observed: none
- Missing local `Name` fields observed: none
- Missing local `Source URL` fields observed: none
- Deleted or moved corpus entries observed: none

## Range checks

| File | Expected range | Manual result |
|---|---:|---|
| `prompt-corpus/famous-prompts.md` | PR001–PR020 | consecutive headings and matching ID fields present |
| `prompt-corpus/famous-prompts-pr021-pr040.md` | PR021–PR040 | consecutive headings and matching ID fields present |
| `prompt-corpus/famous-prompts-pr041-pr060.md` | PR041–PR060 | consecutive headings and matching ID fields present |
| `prompt-corpus/famous-prompts-pr061-pr080.md` | PR061–PR080 | consecutive headings and matching ID fields present |
| `prompt-corpus/famous-prompts-pr081-pr100.md` | PR081–PR100 | consecutive headings and matching ID fields present |
| `prompt-corpus/famous-prompts-pr101-pr120.md` | PR101–PR120 | consecutive headings and matching ID fields present |
| `prompt-corpus/famous-prompts-pr121-pr130.md` | PR121–PR130 | consecutive headings and matching ID fields present |

## Registry triage after inspection

| Status | Count | Meaning in this pass |
|---|---:|---|
| reviewed | 10 | structured local entry or runtime active-source card was inspected for triggers, boundaries, unique behavior, and fallback |
| recovered | 4 | local evidence note and safety boundary exist, but upstream source was not reverified |
| raw | 116 | preserved discovery candidate or runtime-cited summary still needing source-specific review |

Content-level inventory:

- `structured-review`: 4 — PR001, PR002, PR011, PR025
- `evidence-note`: 4 — PR061, PR081, PR106, PR109
- `excerpt-or-paraphrase`: 122

Runtime linkage:

- active and pattern source: 6 — PR002, PR026, PR086, PR089, PR091, PR093
- active source only: 1 — PR065
- pattern source only: 32
- not currently linked to runtime: 91

## Important boundary

`reviewed` in this report means the local repository artifact was structurally reviewed. It does not mean the upstream prompt was authenticated, externally reproduced, or proven effective.

No entry is `tested`, `verified`, or `rejected` yet.

## Duplicate and malformed-entry boundary

No duplicate heading or malformed range placement was observed during the complete manual range scans. The committed validator performs the deterministic exact-count check and should become the merge-time regression check after the workflow exists on the default branch.

The new workflow may not run as a pull-request check until the workflow file itself is present on the default branch. Therefore this report does not claim a completed CI run.

## Next review queue

1. PR088 and PR091 — strongest direct candidates for the coding-agent workflow
2. PR120 and PR122 — persistent instruction pattern currently relies on summary-level evidence
3. PR061, PR064, and PR106 — structured output / extraction
4. PR109 plus one primary retrieval source — grounded research
5. PR110 and PR118 — evaluation rubric and testing workflow
