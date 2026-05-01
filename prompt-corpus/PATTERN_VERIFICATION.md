# Pattern Verification

## Scope

This document checks whether selected patterns in `PATTERN_LESSONS_INDEX.md`
are supported by the current local corpus entries, or whether they read more
like generic prompt-engineering categories.

Only the current repository corpus text was used. No source URLs were opened or
new external evidence was researched.

Files checked:

- `prompt-corpus/PATTERN_LESSONS_INDEX.md`
- `prompt-corpus/famous-prompts.md`
- `prompt-corpus/famous-prompts-pr021-pr040.md`
- `prompt-corpus/famous-prompts-pr061-pr080.md`
- `prompt-corpus/famous-prompts-pr081-pr100.md`
- `prompt-corpus/famous-prompts-pr101-pr120.md`

## 1. Interface Emulation

### Pattern name

Interface emulation

### Claimed reusable move

`Return simulated [tool/interface] output only; do not claim real execution.`

### Related source entries from PATTERN_LESSONS_INDEX.md

- PR002 - Act as Linux Terminal
- PR005 - Act as JavaScript Console
- PR006 - Act as Excel Sheet

### Evidence found in current corpus entries

PR002 is strongly aligned with the pattern. Its corpus entry describes a prompt
that asks the model to act like a Linux terminal and return terminal-style
output only. The entry explicitly says the prompt uses "a strict output-only
constraint" and that the assistant replies "as if it were the terminal surface."
Its pattern lesson says tool-emulation prompts work by narrowing the assistant
to one interface and that simulation must be labeled as simulation. Its failure
mode also identifies the main risk: invented command outputs, file contents,
system state, versions, or errors.

PR005 partially supports the pattern. The entry describes a JavaScript console
simulation that "locks response format to console-style output and suppresses
extra explanation by default." It also warns that outputs should be verified in
a real runtime.

PR006 partially supports the pattern. The entry describes spreadsheet-like
interaction in plain text, with grid/cell conventions and pseudo-tabular
operations. It warns that calculations should be rechecked externally.

### What is source-specific vs generic

Source-specific:

- PR002 directly supports terminal-surface emulation, output-only behavior, and
  the risk of fabricated execution.
- PR005 supports console-output shaping and runtime-verification risk.
- PR006 supports spreadsheet/grid interface simulation and external checking of
  correctness.

Generic:

- The broader phrase "simulate a tool or UI surface" is an abstraction across
  the entries, not a single source phrase.
- The exact reusable move combines the positive interface constraint with a
  safety boundary about not claiming real execution. That boundary is explicit
  in PR002 and implied by PR005/PR006 safety notes.

### Verdict

corpus-supported

### What source excerpt or entry upgrade is needed next

PR005 and PR006 should be upgraded to the fuller PR002-style entry format:
`Pattern lesson`, `Mechanism`, `Failure mode`, and `Reusable move`. This would
make the cross-source induction clearer instead of relying on brief summaries.

## 2. Defensive Jailbreak Analysis

### Pattern name

Defensive jailbreak analysis

### Claimed reusable move

`Classify the attack mechanism; do not reproduce runnable jailbreak text.`

### Related source entries from PATTERN_LESSONS_INDEX.md

- PR025 - ChatGPT DAN Repository
- PR026 - LLM Jailbreaks
- PR027 - ChatGPT DAN Jailbreak Gist
- PR028-PR032 - DAN / anti-DAN community history

### Evidence found in current corpus entries

PR025 strongly supports the pattern. Its entry describes DAN-style prompts as
alternate-persona framing that pressures bypass behavior. The structure summary
names role reassignment, dual-response framing, fictional identity,
urgency/pressure devices, policy-avoidance language, and pseudo-token
reward/punishment mechanics. Its reusable move says safety reviews should
classify jailbreaks by mechanism: identity override, hierarchy inversion,
dual-channel response, reward/punishment pressure, or fake system authority. It
also explicitly says not to reproduce runnable jailbreak text.

PR026 supports the pattern at a summary level. It describes a cross-model
adversarial prompt collection and names risky structures such as authority
override, fictional framing, and instruction conflict. Its safety note says to
keep the source as a defensive reference only and not include runnable jailbreak
prompts in user-facing templates.

PR027 supports the "do not reproduce operational text" boundary but has less
mechanism detail. It describes a single-file historical artifact focused on
adversarial roleplay prompt patterns and says to store metadata and structural
notes only.

PR028 through PR032 support the historical and structural framing, but mostly
through short summaries. They mention roleplay-based policy evasion, versioning
and escalation language, pseudo-commands and state-machine cues, over-refusal
inversion, fictional persona framing, and instruction hierarchy confusion. They
also repeatedly warn against preserving runnable jailbreak instructions.

### What is source-specific vs generic

Source-specific:

- PR025 directly supports the mechanism taxonomy used in the index.
- PR026 directly supports defensive-only handling and names recurring structures
  such as authority override, fictional framing, and instruction conflict.
- PR030 specifically supports command/state-machine framing as a jailbreak
  control metaphor.
- PR031 supports analysis of the opposite failure mode: over-refusal or
  safety-satire inversion.
- PR032 supports fictional persona and hierarchy-confusion analysis.

Generic:

- The index's phrase "defensive prompt-safety artifact" is a synthesized safe
  handling frame, not a phrase shown across the brief entries.
- PR028-PR032 are mostly metadata-level summaries. They justify a defensive
  category, but they do not yet provide enough local excerpt detail to validate
  each mechanism in depth.

### Verdict

corpus-supported

### What source excerpt or entry upgrade is needed next

Add non-operational source excerpts or structured notes to PR026-PR032. The
upgrade should preserve mechanism labels and avoid runnable jailbreak wording.
Useful fields would be: `Observed mechanism`, `Unsafe text omitted`, `Why this
is adversarial`, and `Defensive lesson`.

## 3. Coding-Agent Workflow

### Pattern name

Coding-agent workflow

### Claimed reusable move

`Inspect context -> make smallest safe change -> validate -> summarize diff.`

### Related source entries from PATTERN_LESSONS_INDEX.md

- PR082 - Cursor Rules
- PR083 - Cline
- PR084 - Roo Code
- PR085 - Open Interpreter
- PR086 - Aider
- PR087 - Continue
- PR088 - GPT Engineer

### Evidence found in current corpus entries

There is a source-number mismatch between `PATTERN_LESSONS_INDEX.md` and the
current corpus files. In `famous-prompts-pr081-pr100.md`, PR082 through PR085
are Fabric extraction, summarization, art-prompt, and claim-analysis patterns.
They do not support the coding-agent workflow pattern as cited.

The current corpus entries that actually relate to coding-agent workflows are:

- PR086 - Cursor Rules / `.cursorrules` Pattern
- PR087 - Cursor Directory Rules
- PR088 - Cline System Prompt Lineage
- PR089 - Roo Code / Roo-Code Agent Prompts
- PR090 - Open Interpreter System Prompt Lineage
- PR091 - Aider Coding Prompts
- PR092 - Continue.dev Prompt Templates
- PR093 - GPT Engineer Prompt Lineage

PR086 supports persistent repo-local coding instructions. It describes rules
for coding style, architecture, tests, and framework conventions. This supports
the "inspect context" and "avoid broad generic behavior" parts only indirectly.

PR087 supports adaptation to actual repo context. Its safety note says to adapt
rules to the actual repo and not blindly import framework rules. This supports
the "inspect context" part, but not the full workflow loop.

PR088 strongly supports coding-agent workflow. It describes Cline instructions
for planning, editing files, using tools, reporting results, stepwise coding
work, constraints, and user confirmation points. Its safety note says tool-using
prompts need permission boundaries and file-change review.

PR089 supports mode-based coding-agent behavior across coding, debugging, and
task execution, but the entry is short and does not explicitly mention smallest
safe changes or validation.

PR090 supports local tool execution expectations, runtime feedback, approval,
and sandboxing. This supports the tool-safety and validation boundary, but not
the full edit workflow.

PR091 strongly supports the git/file-editing part. It describes AI-assisted code
editing through repository context, diffs, edit format, and commit-aware
changes. Its safety note says to review patches and tests.

PR092 supports codebase-aware assistance embedded into IDE configuration and
command templates. It also warns about secrets in prompt context and generated
logs, but the entry does not spell out the inspect-edit-test-summarize loop.

PR093 supports software-generation agents that convert requirements into
clarifying questions, project plans, and generated code artifacts. Its safety
note says generated projects require security review, tests, and dependency
checks.

### What is source-specific vs generic

Source-specific:

- PR088 supports planning, tool use, file editing, constraints, reporting, and
  confirmation points.
- PR091 supports repository context, diffs, edit formats, commit-aware changes,
  patch review, and tests.
- PR090 supports approval and sandboxing around local tool execution.
- PR093 supports clarifying questions, planning, generated code artifacts, and
  review/testing needs.
- PR086 and PR087 support repo-local rules and framework-specific adaptation.

Generic:

- "Make the smallest safe change" is a strong coding-agent best practice, but
  the current corpus summaries do not directly show it as a source-derived move.
- "Summarize changed files and next action" is compatible with PR088 and PR091,
  but the exact reusable move is synthesized from agent-workflow norms rather
  than explicitly demonstrated in the local entry text.
- The source list in the index appears stale or shifted. As written, the listed
  PR082-PR085 entries do not support coding-agent workflow.

### Verdict

partially corpus-supported

### What source excerpt or entry upgrade is needed next

First, fix the source-entry mapping in a future update: the current supporting
entries appear to be PR086-PR093, not PR082-PR088. Then upgrade PR088 and PR091
with source-specific non-sensitive excerpts or structured notes showing the
actual workflow sequence: inspect repo context, plan, edit, validate, report
diff, and ask before risky/destructive actions. Without that upgrade, the
pattern is plausible but partly generic.

## Verification pass 003 — Persistent instruction, coding workflow, improvement loop

### Persistent project instruction
Verdict: partially corpus-supported

Evidence checked:
- PR114 — Prompt workflow/versioning discussion supports maintained prompt artifacts, but not project-instruction behavior directly.
- PR115 — Complex workflow discussion supports prompt workflows and evaluation, but does not show persistent instruction triggers or priority.
- PR116 — Prompt versioning discussion supports Git/tool-based prompt management, adjacent to persistence but not enough by itself.
- PR120 — ChatGPT Project custom-instruction discussion directly supports persistent instruction layers, scope, and priority concerns.
- PR122 — System-prompt archive metadata supports structural study of instruction layering, tool rules, and assistant behavior constraints.

Concerns:
- The strongest local evidence is PR120 and PR122, while the index currently emphasizes PR114-PR116 and PR122.
- Current entries are mostly summaries, so trigger/default behavior/boundary examples are inferred from structure rather than verified source excerpts.

Recommended follow-up:
- Add concise evidence notes to PR120 and PR122 showing trigger, scope, priority, boundary, and fallback structure.

### Coding-agent workflow
Verdict: partially corpus-supported

Evidence checked:
- PR086 — Cursor rules support repo-local coding instructions for style, architecture, tests, and framework conventions.
- PR087 — Cursor Directory supports adapting rules to the actual repo rather than blindly importing generic rules.
- PR088 — Cline supports planning, editing files, tool use, reporting results, constraints, and confirmation points.
- PR090 — Open Interpreter supports local tool execution expectations, runtime feedback, approval, and sandboxing concerns.
- PR091 — Aider supports repository context, diffs, edit format, commit-aware changes, patch review, and tests.
- PR093 — GPT Engineer supports clarifying questions, project plans, generated code artifacts, and review/testing needs.

Concerns:
- Local entries support the broad workflow, but "smallest safe change" and "summarize diff" remain partly synthesized from coding-agent practice.
- PR088 and PR091 are the strongest matches but still need source-specific evidence notes.

Recommended follow-up:
- Upgrade PR088 and PR091 with concise evidence notes for inspect, plan, edit, validate, report, and permission boundaries.

### Prompt improvement loop
Verdict: corpus-supported

Evidence checked:
- PR011 — Prompt Enhancer directly supports diagnosing missing control points, rewriting the prompt, and naming what changed.
- PR036 — Micro-prompts support lightweight prompt improvement and redirection, but only as compact add-ons rather than a full loop.
- PR106 — Clarity/anti-hallucination prompt supports asking clarifying questions and surfacing uncertainty before answering.
- PR111 — Prompt evaluator meta-prompt supports rubric-style review and improvement across clarity, context, task definition, output format, examples, and constraints.

Concerns:
- PR011 is the main direct evidence; PR036 and PR106 are supporting or adjacent rather than full prompt-improvement loops.
- PR111 is a stronger evaluator/improver source than the current index relationship suggests, but it is not listed under this pattern.

Recommended follow-up:
- Add or strengthen PR111 evidence notes before deciding whether the index should cite it for Prompt improvement loop.
