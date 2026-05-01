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

## Second Verification Scope

This second pass checks three remaining core patterns from
`PATTERN_LESSONS_INDEX.md` against the current local corpus entries.

Only the current repository corpus text was used. No source URLs were opened or
new external evidence was researched.

Additional files checked for this pass:

- `prompt-corpus/PATTERN_LESSONS_INDEX.md`
- `prompt-corpus/famous-prompts.md`
- `prompt-corpus/famous-prompts-pr021-pr040.md`
- `prompt-corpus/famous-prompts-pr061-pr080.md`
- `prompt-corpus/famous-prompts-pr101-pr120.md`

## 4. Grounded Research

### Pattern name

Grounded research

### Claimed reusable move

`Search/inspect sources -> cite claims -> mark unknowns -> separate recommendation from evidence.`

### Related source entries from PATTERN_LESSONS_INDEX.md

- PR039 - OpenAI student use-case pack
- PR040 - Student-voted prompt roundup
- PR106 - Anti-hallucination / clarity prompt
- PR111 - RAG / retrieval quality discussion

### Evidence found in current corpus entries

PR039 weakly supports the pattern. Its entry is an official student use-case
pack organized around study, writing, planning, creativity, and productivity
tasks. The entry shows mainstream research-adjacent uses, but it does not
describe source citation, unknown marking, evidence separation, or a
recommendation workflow.

PR040 weakly supports the pattern. Its entry is a journalism-style roundup of
student-voted prompts and practical use cases. Its safety note says article
summaries may omit context or exact wording and that original sources are
preferred when available. That supports source-quality caution, but not the
full grounded research loop.

PR106 partially supports the pattern. Its entry describes a structured prompt
for asking clarifying questions and avoiding unsupported claims. It explicitly
mentions assumptions, counter-hypotheses, confidence checks, clarification
triggers, uncertainty handling, and the need for source grounding and
evaluation. This supports "mark unknowns" and "do not make unsupported claims,"
but it does not by itself show source inspection, citation, or recommendation
separation.

There is a source-number mismatch for PR111. `PATTERN_LESSONS_INDEX.md`
describes PR111 as "RAG / retrieval quality discussion," but the current corpus
entry PR111 is "10x Prompt Evaluator," a prompt-improver/evaluator prompt that
uses rubric dimensions such as clarity, context, task definition, output
format, examples, and constraints. The current RAG / retrieval quality entry is
PR109, not PR111. PR109 would support retrieval-first grounding and warns that
RAG quality depends on retrieval quality, but PR109 is not listed for this
pattern in the index.

### What is source-specific vs generic

Source-specific:

- PR040 supports a source-quality warning: article summaries may omit context
  or exact wording, so original sources are preferable.
- PR106 supports assumptions, counter-hypotheses, confidence checks,
  clarification triggers, uncertainty handling, and the need for source
  grounding.
- PR109, if used instead of PR111, would support retrieval-first answering and
  retrieval-quality caution.

Generic:

- The full sequence "search/inspect sources -> cite claims -> mark unknowns ->
  separate recommendation from evidence" is mostly synthesized from research
  best practices rather than directly shown in the cited entries.
- PR039 and PR040 are student-use and prompt-roundup sources, not strong
  evidence for a general grounded-research prompt workflow.
- The index's PR111 citation is stale or misnumbered for this pattern.

### Verdict

partially corpus-supported

### What source excerpt or entry upgrade is needed next

Fix the source-entry mapping so the RAG / retrieval-quality support points to
PR109, or add a real PR111-style grounded-research entry if the numbering is
intended. Upgrade PR039, PR040, PR106, and PR109 with structured notes showing
the specific research workflow steps: inspect sources, cite claims, label
unknowns, separate evidence from inference, and make recommendations only after
the evidence is shown.

## 5. Structured Output / Extraction

### Pattern name

Structured output / extraction

### Claimed reusable move

`Define fields, null policy, evidence rule, and exact output shape.`

### Related source entries from PATTERN_LESSONS_INDEX.md

- PR061 - Anthropic Prompt Library
- PR062 - OpenAI Cookbook
- PR064 - Learn Prompting
- PR106 - Prompt for Seeking Clarity and Avoiding Hallucinating

### Evidence found in current corpus entries

PR061 partially supports the pattern. Its entry describes official prompt
examples across writing, analysis, coding, and productivity tasks. Its
structure summary says the examples are task-oriented recipes with clear role,
context, and output expectations. This supports output expectations at a broad
level, but does not specifically show field definitions, null policy, or
evidence rules.

There is a naming mismatch for PR062. `PATTERN_LESSONS_INDEX.md` labels it as
OpenAI Cookbook, but the current corpus entry PR062 is Anthropic Prompt
Engineering Overview. The current PR062 still supports structured output at a
summary level: it describes prompt design as specifying task, context,
constraints, examples, and output shape. It does not explicitly mention null
policy or evidence text.

There is also a naming mismatch for PR064. `PATTERN_LESSONS_INDEX.md` labels it
as Learn Prompting, but the current corpus entry PR064 is OpenAI Prompt
Examples / Cookbook. The current PR064 strongly supports the pattern. Its short
excerpt names structured outputs, classification, extraction, retrieval, and
assistant workflows. Its structure summary says the examples combine task
framing, input data, output schema, and validation ideas.

PR106 partially supports the evidence and missing-information side of the
pattern. Its entry describes assumptions, counter-hypotheses, confidence
checks, and clarification triggers, and warns that anti-hallucination prompts
still require source grounding and evaluation. This supports uncertainty and
evidence discipline, but does not directly show an extraction schema or null
policy.

### What is source-specific vs generic

Source-specific:

- PR064 directly supports structured outputs, classification, extraction,
  output schema, and validation ideas.
- PR062 supports specifying output shape as part of prompt design.
- PR061 supports prompt examples with clear output expectations.
- PR106 supports source grounding, confidence checks, and clarification
  triggers.

Generic:

- "Null policy" is not directly supported by the current local entry summaries.
- "Evidence rule" is compatible with PR106 and PR064, but the exact extraction
  rule is not shown in local excerpts.
- The index names for PR062 and PR064 appear stale or shifted, even though the
  current IDs still partly support the pattern.

### Verdict

corpus-supported

### What source excerpt or entry upgrade is needed next

Add source-specific examples or structured notes to PR064 showing exact schema,
missing-value behavior, and validation expectations. Add a short note to PR106
connecting uncertainty handling to extraction outputs: when evidence is absent,
return null or ask a clarification question rather than inventing a value. Fix
the PR062 and PR064 display names in the index in a future update.

## 6. Evaluation Rubric

### Pattern name

Evaluation rubric

### Claimed reusable move

`Define criteria, scoring anchors, pass/fail rules, and failure examples.`

### Related source entries from PATTERN_LESSONS_INDEX.md

- PR108 - Prompt evaluation rubric discussion
- PR109 - Prompt testing / evaluation discussion
- PR110 - Prompt versioning discussion
- PR118 - Prompt management / PromptOps discussion

### Evidence found in current corpus entries

There are several source-number mismatches between the index labels and the
current corpus entries.

PR108 does not support the evaluation-rubric pattern as cited. The current
entry is a metacognition prompt claim about making the model observe its own
certainty generation or pattern matching. Its safety note says to evaluate
output behavior rather than assuming introspective claims are literally true,
but it is not a rubric discussion.

PR109 does not support the evaluation-rubric pattern as cited. The current
entry is a RAG / hallucination-control claim with a retrieval-first workflow
and a warning that RAG quality depends on retrieval quality. It is more relevant
to grounded research than to rubric design.

PR110 strongly supports part of the pattern. The current entry is "How to
Evaluate the Quality of a Prompt." It describes a rubric-oriented discussion
covering clarity, context, output format, and feasibility. Its safety note says
to prefer behavior-based evals over purely aesthetic prompt scoring. This
supports criteria and behavior-based evaluation, but the local summary does not
show scoring anchors, pass/fail rules, or failure examples.

PR118 partially supports the broader evaluation/testing context. It describes
tools for prompt management and testing, with practical pain points around
prompt libraries, testing, regression checks, and collaboration. This supports
the need for testing infrastructure, but it does not provide a rubric structure.

The current PR111 entry, although not listed for this pattern in the index,
would also support evaluation rubrics. It describes a prompt evaluator using
rubric dimensions such as clarity, context, task definition, output format,
examples, and constraints, and warns that "10x" claims require actual tests.

### What is source-specific vs generic

Source-specific:

- PR110 supports rubric-oriented evaluation using clarity, context, output
  format, and feasibility.
- PR110 supports behavior-based evals over aesthetic scoring.
- PR118 supports testing and regression-check infrastructure as a recurring
  prompt-management need.
- PR111, if added to this pattern, supports evaluator dimensions such as
  clarity, context, task definition, output format, examples, and constraints.

Generic:

- The current cited entries do not show explicit scoring anchors such as pass,
  partial, and fail.
- Failure examples are not visible in the local summaries.
- PR108 and PR109 are stale or wrong citations for this pattern.
- "Prompt versioning discussion" is not the current PR110 label; current PR110
  is the stronger evaluation-rubric source.

### Verdict

partially corpus-supported

### What source excerpt or entry upgrade is needed next

Fix the index mapping so PR110 and PR111 are the primary rubric sources, while
PR118 remains supporting context for testing infrastructure. Upgrade PR110 and
PR111 with non-sensitive source excerpts or structured notes that show actual
criteria, scoring anchors, pass/fail rules, and failure examples. Remove or
replace PR108 and PR109 from this pattern unless future corpus entries provide
rubric-specific evidence for them.
