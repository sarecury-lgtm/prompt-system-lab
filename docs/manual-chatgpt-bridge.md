# PSOS Manual ChatGPT Bridge

The manual bridge keeps PSOS usable when the ChatGPT-authenticated Codex CLI is unavailable or its included usage is exhausted. It does **not** turn the ChatGPT website into an unofficial API. It pauses at each model stage, shows the exact prompt for the current run, accepts the response returned by the user, validates it, and resumes the same run.

## Start

From the repository root:

```powershell
python -B scripts/problem_solving_manual_web.py
```

Open:

```text
http://127.0.0.1:8766
```

The server binds only to a loopback address.

## Basic flow

1. Enter an ordinary request and choose how much external search is allowed.
2. Press **현재 지시문 복사**.
3. After copying succeeds, press **ChatGPT 열기** and paste the prompt.
4. Return the complete ChatGPT response to the bridge.
5. The bridge validates the response and advances the same run to the next stage.
6. Repeat until the user-facing output is complete.

Copying and opening ChatGPT are separate actions. This prevents a new tab from taking focus before the clipboard write finishes and leaving an older clipboard value in place.

The page restores only the run ID saved by that browser. It does not automatically replace the screen with an unrelated latest or completed run from the server.

A `HYBRID` route produces primary and secondary execution handoffs in dependency order. The primary result is passed to the secondary stage, and limitations from both stages are retained.

## Results and records

The completed screen shows and copies the actual `execution.result_markdown`, saved as:

- `output.md` — the user-facing answer, prompt, report, or other final output;
- `result.md` — the full PSOS audit view containing the goal, route, output, and limitations.

The bridge also writes:

- `request.txt`
- `goal_ledger.json`
- `route.json`
- `manual-handoff.json`
- stage prompt files
- normalized and raw responses
- timestamps and SHA-256 values

## Compare a completed PROMPT result

A completed single-route `PROMPT` result includes **프롬프트 구조 비교**. This is a controlled diagnostic, not a normal revision.

The original result is kept as the current baseline. The bridge then creates three alternative executor inputs:

1. remove only the separately repeated raw user-request block;
2. replace the full Goal Ledger with goal, fixed constraints, and completion condition;
3. replace the parallel request/Ledger/baseline surfaces with one `Prompt Build Brief`.

The page walks through three candidate-generation handoffs and one blind assessment handoff. Use a **new ChatGPT conversation for every handoff** so a previous candidate does not influence the next candidate.

The blind assessment hides the internal variant names and compares:

- requirement preservation;
- clarity and priority of the core working procedure;
- semantic repetition and format pressure;
- practical reuse by another AI.

Shorter output is not rewarded by itself. A compressed prompt that loses an important condition is marked down.

The parent run is never overwritten. The child comparison run stores:

```text
prompt_ablation/inputs/*.md
prompt_ablation/results/*.md
prompt_ablation/results/*.json
prompt_ablation/results/blind_assessment.json
prompt_ablation/comparison.json
prompt_ablation/comparison.md
```

The comparison evaluates the generated prompts themselves. Applying each candidate to the same chart images is a later experiment after the strongest candidates are identified.

## External-information modes

| Mode | Behavior |
|---|---|
| `none` | External web search is unavailable. Use for supplied-file or image analysis, writing, and prompt creation that does not require current facts. |
| `standard` | The router still selects the route. If it selects `RESEARCH`, the execution prompt expects ordinary ChatGPT web search. |
| `deep` | Deep research is used only if the selected route is `RESEARCH`; router and normalization stages remain ordinary ChatGPT stages. |

For `deep` mode:

1. Complete the router handoff in ordinary ChatGPT.
2. At the Deep research report stage, enable Deep research and send the displayed prompt.
3. Return the complete Markdown report without converting it to JSON.
4. The bridge stores that report and creates a normalizer prompt.
5. Send the normalizer through ordinary ChatGPT and return the execution JSON.

## Revise a completed result

The completed-result panel includes **이 결과 수정**.

1. Describe what was wrong or what should take priority instead.
2. Keep **같은 방식으로 결과만 고치기** unless the original goal or output type was misunderstood.
3. Select the external-information mode for the revision.
4. Start the revision.

The original run is not overwritten. The child run records its parent, feedback, revision context, new Goal Ledger, and execution history.

## Optional Chrome extension

The unpacked extension in `extensions/psos-chatgpt-bridge/` reduces the visible transfer steps while retaining explicit user control.

- **현재 PSOS 작업 가져오기** stays bound to the same run until that run completes.
- It refuses to overwrite text already being written in the ChatGPT composer.
- At insertion time it records the current assistant-response baseline.
- **이 작업의 새 답변 반환** accepts only a completed assistant response created after that insertion.
- It refuses to return an older response, a user message, an arbitrary article, or a response that is still streaming.
- When another PSOS stage remains, it inserts that stage but does not press ChatGPT's send button.

ChatGPT DOM selectors can still change independently of repository tests, so real-browser QA remains necessary after major ChatGPT UI changes.

## Router and validation semantics

The manual server applies the same transitional semantic corrections used by the quality runtime:

- `fixed_constraints` may be empty when the user gave no fixed constraint;
- supplied images or context do not imply `RESEARCH` unless external current facts are required;
- single routes must have null primary and secondary routes;
- HYBRID primary and secondary order must reflect an actual dependency;
- `completed`, `partial`, `blocked_by_capability`, and `handoff` fields must be internally consistent;
- HYBRID limitations from both stages are preserved.

## Trust boundary

The manual bridge preserves schema validation, route-specific completion validation, rejection of false local-write claims, and prompt/response audit records. It cannot independently prove browser-side web-search or Deep research tool calls, so manual runs record that limitation.

## Tests

```powershell
python -B -m unittest \
  tests.test_problem_solving_core_semantic_fixes \
  tests.test_manual_web_assets \
  tests.test_manual_output_copy \
  tests.test_problem_solving_manual_web \
  tests.test_problem_solving_manual_revision \
  tests.test_problem_solving_manual_deep \
  tests.test_problem_solving_manual_prompt_ablation \
  tests.test_problem_solving_manual_http
```
