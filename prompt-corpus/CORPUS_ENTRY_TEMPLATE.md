# Corpus Entry Template

## Purpose

Use this template when adding or upgrading prompt corpus entries.

The old corpus format was good for cataloging sources, but too shallow for learning. This template adds fields that force each entry to explain what reusable prompt-design pattern the source teaches.

## Core Entry Template

```markdown
### PR### — [Name]

- **ID:** PR###
- **Name:** [source / prompt name]
- **Source URL:** [url]
- **Platform:** [GitHub / Reddit / Official Docs / Paper / Marketplace / etc.]
- **Type:** [role prompt / meta-prompt / coding-agent rule / eval prompt / jailbreak-history / etc.]
- **Source status:** [official / community / historical / unverified / controversial / mirrored]

## Short excerpt
[One short allowed excerpt or paraphrase. Avoid long copied prompt text.]

## Structure summary
[How the prompt/source is built. Mention roles, sections, variables, examples, constraints, workflow, tools, scoring, etc.]

## Pattern lesson
[The reusable design pattern this entry teaches. This is the most important field.]

## Mechanism
[Why the pattern appears to work, or what model behavior it tries to control.]

## Failure mode
[How this pattern can fail, be overused, or be misused.]

## Reusable move
[One compact prompt-design move that can be reused elsewhere.]

## Tags
`tag1`, `tag2`, `tag3`

## Safety / reproduction note
[What not to copy, what to verify, or how to handle safely.]
```

## Field Guidance

### Short excerpt
Use this for a small traceable sample only. Do not copy long copyrighted, paid, or proprietary prompt text.

### Structure summary
Describe the shape of the artifact.

Good:

> Uses a role assignment, strict output-only constraint, and repeated user-command / assistant-output loop.

Weak:

> It is a useful prompt.

### Pattern lesson
Explain what the entry teaches.

Good:

> Interface-emulation prompts work by narrowing the assistant into a simulated input/output surface, but they need a clear warning that outputs are simulated and not real execution.

Weak:

> This is a canonical example of terminal emulation.

### Mechanism
Explain the control lever.

Examples:

- narrows output format
- separates instruction from data
- forces null handling
- creates a review loop
- adds evidence requirements
- turns a vague role into a workflow
- converts a one-shot answer into a stateful process

### Failure mode
Name the predictable problem.

Examples:

- hallucinated command results
- overlong scaffolding
- false confidence
- prompt injection exposure
- roleplay overpowering the actual task
- unverified popularity claims
- brittle JSON formatting

### Reusable move
Make the lesson portable.

Example:

> Add a `simulated output only, not real execution` boundary whenever asking the model to emulate a tool.

## Upgraded Example — PR002

```markdown
### PR002 — Act as Linux Terminal

- **ID:** PR002
- **Name:** Act as Linux Terminal
- **Source URL:** https://github.com/f/prompts.chat
- **Platform:** GitHub
- **Type:** role simulation / tool emulation
- **Source status:** community / historical

## Short excerpt
Asks the model to act like a Linux terminal and return terminal-style output only.

## Structure summary
Uses a role assignment, a strict output-only constraint, and repeated command-response turns. The user supplies shell-like commands; the assistant replies as if it were the terminal surface.

## Pattern lesson
Tool-emulation prompts work by shrinking the assistant into a narrow interface. The core pattern is not “act as X”; it is “only expose the output surface of X.” This can be useful for teaching or mock interaction, but it must be labeled as simulation.

## Mechanism
The prompt suppresses normal assistant explanation and forces a specific response channel: terminal output. This reduces conversational drift but increases risk of fabricated execution results.

## Failure mode
The model may invent command outputs, file contents, system state, package versions, or errors. Users may mistake simulated output for real execution.

## Reusable move
When simulating a tool, define both the output surface and the boundary: “Return simulated output only; do not claim commands actually ran.”

## Tags
`simulation`, `terminal`, `tool-emulation`, `format-control`

## Safety / reproduction note
Treat outputs as simulated text, not execution. Never assume command results are real.
```

## Upgraded Example — PR025

```markdown
### PR025 — ChatGPT DAN Repository

- **ID:** PR025
- **Name:** ChatGPT DAN Repository
- **Source URL:** https://github.com/0xk1h0/chatgpt_dan
- **Platform:** GitHub
- **Type:** jailbreak-history collection
- **Source status:** community / adversarial / historical

## Short excerpt
DAN-style prompts use alternate-persona framing to pressure the model into bypass behavior.

## Structure summary
Uses role reassignment, dual-response framing, fictional identity, urgency/pressure devices, and policy-avoidance language. Some variants add pseudo-token penalties or reward/punishment mechanics.

## Pattern lesson
The reusable lesson is defensive: adversarial prompts often try to create a second identity that is framed as less constrained than the assistant. The attack pattern is not merely “ignore rules”; it is “delegate responsibility to a fictional persona.”

## Mechanism
Dual-persona framing attempts to split the model’s behavior into compliant and non-compliant channels, making the unsafe channel feel like a roleplay continuation rather than a direct policy violation.

## Failure mode
Storing or improving executable jailbreak text can make the corpus unsafe and less useful. It also encourages prompt design based on coercion rather than task clarity.

## Reusable move
For safety reviews, classify jailbreaks by mechanism: identity override, hierarchy inversion, dual-channel response, reward/punishment pressure, or fake system authority.

## Tags
`DAN`, `jailbreak-history`, `adversarial`, `safety`, `dual-persona`

## Safety / reproduction note
Do not reproduce runnable jailbreak text. Keep only structural and defensive analysis.
```
