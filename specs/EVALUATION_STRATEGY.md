# Evaluation strategy

## Current problem
- Manual real runs exist, but most are PASS-oriented.
- Runner and evaluator are not consistently separated.
- The repo needs PARTIAL/FAIL examples to prove that specs can catch weak prompts.

## Decision for now
- Do not adopt promptfoo immediately.
- Continue manual real runs for now.
- Improve trust by separating runner and evaluator where possible.
- Add at least one PARTIAL or FAIL run before introducing more tooling.
- Revisit promptfoo after the manual process has clearer failure examples.

## Why not promptfoo yet
- It is useful for declarative test cases and assertions.
- But adding it now would introduce tooling overhead before the manual evaluation method is mature.
- The repo should first prove what it wants to measure.

## Near-term evaluation rules
- Prefer runner != evaluator.
- Record raw output before evaluation.
- Do not edit raw output.
- Include model/session metadata or mark unknown.
- Include at least one non-PASS run.
- Map each spec/run to the pattern it is testing where possible.

## Next recommended runs
1. A deliberately overbuilt prompt that should receive PARTIAL or FAIL.
2. A prompt-rewrite run evaluated by a different model/session.
3. A structured-output example tied to one example file.
