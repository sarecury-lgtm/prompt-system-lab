# Task 000: Collect Verified Prompts

## Goal

Start a separate track for collecting verified prompts before turning them into reusable prompt-system patterns.

This track should not replace the existing prompt corpus. It adds a stricter intake path:

1. Collect prompts with clear source evidence.
2. Verify provenance, usage context, and reproduction boundaries.
3. Decompose each prompt into mechanisms and assumptions.
4. Extract reusable patterns only after verification.

## Scope

In scope:
- Public prompts, official examples, documented system prompts, and source-traceable prompt artifacts
- Prompts with enough context to explain who used them, for what task, and under what constraints
- Short excerpts, structural summaries, and attribution links
- Notes about what can and cannot be reused safely

Out of scope:
- Unsourced viral prompt screenshots
- Proprietary or paid prompt dumps
- Long verbatim copied prompt text
- Jailbreak material except as defensive or historical structure notes
- Pattern claims that cannot be tied back to source evidence

## Intake Checks

For each candidate prompt, record:

- Source URL or local source path
- Author, organization, or publisher when known
- Publication or retrieval date when available
- Task domain and intended user
- Prompt role, input contract, output contract, and constraints
- Evidence that the prompt is real, used, or officially documented
- Copyright or reuse boundary
- Reasons to reject, hold, or accept the prompt

## Initial Workflow

1. Create a small queue of source-traceable prompt candidates.
2. Reject candidates with unclear provenance or unsafe copying risk.
3. For accepted candidates, store only short compliant excerpts and structural notes.
4. Decompose accepted prompts into components, assumptions, and failure modes.
5. Promote repeated mechanisms into pattern lessons only after multiple examples support them.

## Done Criteria

- At least one verified prompt candidate has complete source and context notes.
- Any copied text stays short and compliant.
- The existing `prompt-corpus/`, `skills/`, `specs/`, and `PATTERN_VERIFICATION` structure remains unchanged.
- Follow-up work is clear enough to continue collection without rewriting this task.
