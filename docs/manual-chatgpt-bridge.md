# PSOS Manual ChatGPT Bridge

The manual bridge keeps PSOS usable when the ChatGPT-authenticated Codex CLI is unavailable or its included usage is exhausted. It does **not** turn the ChatGPT website into an unofficial API. Instead, it pauses at each model stage, produces the exact prompt and JSON contract, accepts the response returned by the user, validates it with the canonical PSOS validators, and resumes the run.

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

1. Enter an ordinary request.
2. Copy the generated router prompt into ChatGPT.
3. Paste ChatGPT's JSON response into the bridge.
4. The bridge validates the router result and produces the execution prompt.
5. Return the execution JSON in the same way.
6. The bridge writes the normal PSOS records:
   - `request.txt`
   - `goal_ledger.json`
   - `route.json`
   - `result.md`
7. It also writes `manual-handoff.json`, prompt files, normalized JSON responses, raw responses, timestamps, and SHA-256 values for the complete manual transfer history.

A `HYBRID` route produces one additional execution handoff.

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

It cannot independently verify that the ChatGPT browser actually invoked web search or another browser-side tool. A manual run therefore records this limitation in the final result and sets `manual_bridge.independent_browser_tool_receipts` to `false` in `route.json`.

## Supported first version

| Route | Manual bridge behavior |
|---|---|
| `DIRECT` | Supported |
| `RESEARCH` | Supported when ChatGPT actually searches and returns web evidence; browser tool calls are not independently receipted |
| `PROMPT` | Supported and still uses the local Prompt Compiler baseline |
| `CODE` | Supports code or patch proposals; rejects claims that local files were already changed |
| `PROJECT` | Supports the closest read-only result or handoff; rejects local write claims |
| `REUSE` | Must return `handoff` or `blocked_by_capability` in this first version |
| `HYBRID` | Supported through primary and secondary manual stages |

## Tests

```powershell
python -B -m unittest tests.test_problem_solving_manual_web
```
