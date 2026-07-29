# Usage

This repo separates work into four layers:

1. corpus evidence
2. pattern lessons
3. operational skills/examples
4. specs/real runs

Most public references cover only one layer. Use [`references/external-projects.md`](references/external-projects.md) to see which adjacent projects inform which layer.

## 0. Solving an ordinary request

Run the Personal Problem-Solving OS from the repository root:

```powershell
python scripts/problem_solving_os.py --request "내 요청"
```

Add UTF-8 context when needed:

```powershell
python scripts/problem_solving_os.py --request "이 문맥을 반영해 해결해 줘" --context-file path/to/context.md
```

The runtime reuses the installed, ChatGPT-subscription-authenticated Codex CLI. It does not require
`OPENAI_API_KEY`. Each run saves `request.txt`, `goal_ledger.json`, `route.json`, and `result.md`
under `runs/<run-id>/`. Live research is used only when the CLI exposes web search. Workspace
changes are read-only unless `--allow-workspace-write` is explicitly supplied together with the
intended `--workspace`.

When a `CODE` or `PROJECT` stage receives workspace-write, the runtime snapshots the approved
workspace before and after the Codex invocation. It saves
`<stage>-workspace-receipt.json` and rejects completion when a claimed `created`/`modified`
artifact did not actually change, an unreported file changed, a file was deleted, or a claimed
path escapes the approved workspace.

For a completed `REUSE` stage, the runtime requires at least one exact local asset path. It verifies
that each cited or inspected asset exists inside the approved workspace, fingerprints files and
bounded directories, and saves `<stage>-reuse-receipt.json`. Missing, external, symlinked, or overly
broad directory claims are rejected instead of being presented as inspected assets.

Model and tool selection is explicit in
[`problem-solving-project/model-policy.json`](problem-solving-project/model-policy.json):

- Luna low routes the request without executing it.
- Terra low/medium handles `DIRECT` and `REUSE`.
- Sol medium handles `RESEARCH` and `PROMPT`.
- Sol high handles `CODE` and `PROJECT`.
- invalid Luna routing falls back once to Sol medium; invalid Terra execution falls back once to
  Sol medium.
- only `RESEARCH` receives live search, and only explicitly approved `CODE`/`PROJECT` runs request
  workspace write.
- `PROMPT` first builds a baseline with the existing Prompt Compiler, then gives that baseline and
  any upstream research to Sol for one final ready-to-use prompt. HYBRID exposes only the downstream
  final result while preserving upstream evidence in `route.json`.

`route.json` records the planned and actual model, reasoning effort, search setting, sandbox, and
fallback outcome for every model invocation. Override the policy only when testing a reviewed
replacement:

```powershell
python scripts/problem_solving_os.py --request "..." --model-policy path/to/model-policy.json
```

## 1. Designing a new prompt

- Easiest user-facing path: [`chatgpt-project/README.md`](chatgpt-project/README.md)
- Start here: [`skills/prompt-design-workflow.md`](skills/prompt-design-workflow.md)
- Give the AI: the goal, audience, input type, output shape, and any hard constraints
- Expected output: a usable prompt that is short, specific, and testable
- Avoid: decorative roles, giant rule piles, and prompts that do not say what to do when information is missing
- Copy-paste instruction: `Turn this goal into a usable prompt. Use the smallest matching pattern from PATTERN_LESSONS_INDEX.md and give me the final prompt only unless I ask for notes.`

## 2. Improving an existing prompt

- Start here: [`skills/prompt-rewrite.md`](skills/prompt-rewrite.md)
- Give the AI: the original prompt, the real goal, the intended user, and any output requirements
- Expected output: a cleaner rewrite plus a brief note about what changed
- Avoid: keeping impossible absolutes, adding extra assumptions, or making the prompt longer without making it clearer
- Copy-paste instruction: `Rewrite this prompt for clarity and control. Preserve the real goal, remove clutter, and keep the output easy to paste.`

## 3. Analyzing a prompt

- Start here: [`skills/prompt-analysis.md`](skills/prompt-analysis.md)
- Give the AI: the prompt text and the context it is meant to run in
- Expected output: a verdict, the main strengths and weaknesses, and a better version or next edit
- Avoid: analysis that only repeats the prompt, or vague feedback with no concrete failure point
- Copy-paste instruction: `Analyze this prompt with a quick verdict, why, best part, weak point, and better version.`

## 4. Adding a new source / corpus entry

- Start here: [`references/source-index.md`](references/source-index.md)
- Give the AI: the source URL, the source type, the corpus range, and any safe excerpt or structure summary
- Expected output: a source-traceable corpus entry with short excerpt, structure summary, pattern lesson, mechanism, failure mode, reusable move, tags, and safety note
- Avoid: copying long proprietary text, inventing source IDs, or upgrading a source without traceable evidence
- Copy-paste instruction: `Add this source as a corpus entry with a short excerpt, structure summary, and reusable move. Keep the text traceable and concise.`

## 5. Verifying a pattern

- Start here: [`prompt-corpus/PATTERN_LESSONS_INDEX.md`](prompt-corpus/PATTERN_LESSONS_INDEX.md) and [`prompt-corpus/PATTERN_VERIFICATION.md`](prompt-corpus/PATTERN_VERIFICATION.md)
- Give the AI: the pattern name and the current corpus entries to compare against
- Expected output: a corpus-supported / partially corpus-supported / weakly corpus-supported / not corpus-supported judgment with evidence and follow-up
- Avoid: web research, invented source IDs, or calling a pattern supported when the corpus only gives indirect evidence
- Copy-paste instruction: `Verify this pattern against the current corpus only. Show evidence checked, concerns, and a concise follow-up.`

## 6. Recording a real run

- Start here: [`specs/runs/REAL_RUN_TEMPLATE.md`](specs/runs/REAL_RUN_TEMPLATE.md)
- Give the AI: the exact prompt sent to the model, the raw model output, the model/settings if known, and the files loaded
- Expected output: a complete run record with raw input, raw output, result, limitations, and any evaluation notes
- Avoid: paraphrasing the model output, guessing model metadata, or leaving out the exact input prompt
- Copy-paste instruction: `Record this as a real run using the template. Keep raw input/output verbatim and mark unknowns as unknown.`

## 7. Using the repo with different tools

### ChatGPT Project

- Start here: [`chatgpt-project/README.md`](chatgpt-project/README.md)
- Put [`chatgpt-project/PROMPT_COMPILER_INSTRUCTIONS.md`](chatgpt-project/PROMPT_COMPILER_INSTRUCTIONS.md) in Project instructions and add the three listed source files
- Give the AI: an ordinary-language description of what the final prompt should accomplish and any fixed constraints
- Expected output: one task-specific, ready-to-copy prompt followed by a compact routing record
- Avoid: asking the compiler to perform the underlying research, coding, or decision task
- Copy-paste request: `세 가지 대안을 비용과 위험 기준으로 비교하고 최종 선택을 돕는 프롬프트를 만들어줘.`

### Claude chat / Claude Project

- Start here: [`project-instructions/main.md`](project-instructions/main.md), [`skills/prompt-design-workflow.md`](skills/prompt-design-workflow.md), and [`references/external-projects.md`](references/external-projects.md)
- Give the AI: the exact task, the relevant local files, and only the needed reference material
- Expected output: a compact answer or prompt artifact with clear boundaries and fallback behavior
- Avoid: making the repo Claude-only or loading more files than the task needs
- Copy-paste instruction: `Load only the relevant local files, use the corpus-first workflow, and keep the answer compact.`

### Codex CLI

- Start here: [`project-instructions/main.md`](project-instructions/main.md) and the relevant file under `skills/`, `examples/`, `prompt-corpus/`, or `specs/`
- Give the AI: the exact file paths, the change goal, and the validation rule
- Expected output: a repo change plus `git diff --check` and a short summary of what changed
- Avoid: broad refactors, unreviewed file moves, and changes outside the requested scope
- Copy-paste instruction: `Make the smallest safe repo change, validate it, and report only the files changed.`

### Other repo-aware coding assistants

- Start here: [`project-instructions/main.md`](project-instructions/main.md), [`README.md`](README.md), and the specific file you want to change
- Give the AI: the exact repository context, the file(s), and the expected output shape
- Expected output: a narrow repo-aware update that respects the corpus / skills / specs split
- Avoid: mixing pattern catalog work with spec work or file edits with unsupported claims
- Copy-paste instruction: `Stay within the repo layers, use only the requested files, and keep the change reviewable.`

## What to do first

If you are unsure where to begin:

1. Read `README.md`
2. Read `prompt-corpus/PATTERN_LESSONS_INDEX.md`
3. Read the matching skill or example
4. Use `references/external-projects.md` only when you need adjacent inspiration
