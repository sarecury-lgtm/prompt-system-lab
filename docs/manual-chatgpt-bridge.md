# PSOS Manual ChatGPT Bridge

The manual bridge keeps PSOS usable when the ChatGPT-authenticated Codex CLI is unavailable or its included usage is exhausted. It does **not** turn the ChatGPT website into an unofficial API. Instead, it pauses at each model stage, produces the prompt and return contract, accepts the response returned by the user, validates it with the canonical PSOS validators, and resumes the run.

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

1. Enter an ordinary request and choose a RESEARCH mode.
2. Copy the generated router prompt into ChatGPT.
3. Paste ChatGPT's router JSON into the bridge.
4. The bridge validates it and replaces the prompt with the next stage.
5. Send the new prompt to ChatGPT and return the new response.
6. Repeat until the result is complete.

The response box is cleared whenever the stage changes. A `HYBRID` route produces an additional execution handoff.

The bridge writes the normal PSOS records:

- `request.txt`
- `goal_ledger.json`
- `route.json`
- `result.md`

It also writes `manual-handoff.json`, prompt files, normalized responses, raw responses, timestamps, and SHA-256 values for the complete manual transfer history.

## RESEARCH modes

| Mode | Behavior |
|---|---|
| `none` | Router sees no web-search capability. |
| `standard` | The RESEARCH execution prompt expects ordinary ChatGPT web search and an execution JSON response. |
| `deep` | The bridge first asks for a complete Deep research Markdown report, saves it, and then creates a separate normalizer prompt that converts only that report into PSOS execution JSON. |

For `deep` mode:

1. Complete the router handoff normally.
2. When the UI says **심층 리서치 실행**, enable Deep research in ChatGPT and send the displayed prompt.
3. Paste the completed Markdown report into the bridge. Do not convert it to JSON.
4. The bridge saves the report and displays a **보고서 정규화** prompt.
5. Send that prompt through ordinary ChatGPT and return the execution JSON.

The original report remains in the run directory and its path is recorded in `route.json`.

## Revise a completed result

The completed-result panel includes **이 결과 수정**.

1. Describe what was wrong or what should take priority instead.
2. Choose whether the revision should use no search, ordinary search, or Deep research.
3. Start the revision.

The bridge does not overwrite the original run. It creates a new child run containing:

- `revision.json` with the parent run ID and user feedback;
- `revision-context.md` with the prior Goal Ledger, prior result, and correction;
- a new Goal Ledger and execution history.

The child `route.json` records `parent_run_id`, `revision_feedback`, and `research_mode`.

## Optional Chrome extension

The unpacked extension in `extensions/psos-chatgpt-bridge/` reduces the transfer to visible button presses:

- **대기 중 작업 가져오기** inserts the latest pending prompt into the current `chatgpt.com` composer.
- The user reviews it and presses ChatGPT's send button.
- **마지막 답변 반환** extracts the latest assistant response, sends it to the local bridge, and inserts the next PSOS prompt automatically when another stage remains.

The extension intentionally does not press ChatGPT's send button. Full DOM automation would be brittle, could send the wrong context, and would weaken the explicit handoff boundary.

## Trust boundary

The manual bridge preserves:

- Goal Ledger and route schema validation;
- execution schema and route-specific completion validation;
- rejection of `created` or `modified` file claims because the manual ChatGPT session has no local write capability;
- rejection of completed `REUSE` claims because the browser session cannot independently prove local asset inspection;
- prompt and response audit files with SHA-256 values;
- normal PSOS result and route records.

It cannot independently verify that the ChatGPT browser actually invoked web search, Deep research, or another browser-side tool. A manual run therefore records this limitation in the final result and sets `manual_bridge.independent_browser_tool_receipts` to `false` in `route.json`.

## Supported routes

| Route | Manual bridge behavior |
|---|---|
| `DIRECT` | Supported |
| `RESEARCH` | Supported through ordinary web search or the report-plus-normalizer Deep research flow |
| `PROMPT` | Supported and still uses the local Prompt Compiler baseline |
| `CODE` | Supports code or patch proposals; rejects claims that local files were already changed |
| `PROJECT` | Supports the closest read-only result or handoff; rejects local write claims |
| `REUSE` | Must return `handoff` or `blocked_by_capability` |
| `HYBRID` | Supported through primary and secondary manual stages |

## Tests

```powershell
python -B -m unittest tests.test_problem_solving_manual_web tests.test_problem_solving_manual_http
```
