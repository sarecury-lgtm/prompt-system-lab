# PSOS local UI QA report

## Deterministic browser checks

Tested against the live local server and real run data. The existing responsive shell baseline was
captured at the exact target sizes. The new scoped-write interaction was exercised in the connected
browser's fixed 1280×720 viewport.

| Baseline check | 1440×900 | 1920×1080 | 390×844 |
|---|---:|---:|---:|
| Console warnings/errors | 0 | 0 | 0 |
| Page-level horizontal overflow | none | none | none |
| Longest result rendered | 11,986 characters | 11,986 characters | short real result |
| Primary result width | 780px | 780px | 309px |
| Shell width | 1,425px | 1,504px | 343px |
| Status rail width | 340px | 340px | stacked |

The longest real item was `model-route-hybrid-smoke`. It remained readable with a 780px maximum
text measure and did not cause horizontal overflow. The request field, selected `HYBRID` route,
immutable run ID, result, health state, next action, and recent runs remained visible in the desktop
captures.

The read-only end-to-end form check submitted a real request through the browser. The job entered a
visible running state, completed through `REUSE`, displayed the exact Chrome command, exposed one
evidence item and one inspected artifact, re-enabled the submit control, and refreshed status from
17/17 to 18/18 valid runs.

The scoped-write check selected `파일 변경`, entered an exact request and `USAGE.md`, and opened the
approval card without starting a run. The card showed the unchanged request, fixed workspace,
normalized path, ten-minute lifetime, one-time use, deletion ban, outside-scope rollback, and
unreported-change rollback. While that card was pending, the request, mode, path, search, and
submission controls were locked so the displayed approval could not drift from the execution
payload. Selecting `취소` unlocked them, returned a no-change confirmation, and kept the run count at
18/18. A second check submitted `.git/config`; the server rejected it in Korean before an approval
could be created. No real model write was approved during browser QA.

At 1280×720, page scroll width was 1265px against a 1280px viewport, with zero console errors. The
longest real result rendered 12,147 visible characters at the same viewport without horizontal
overflow or console errors. Transaction execution, receipt creation, scope violation, and automatic
rollback are covered by deterministic Python tests instead of a destructive browser exercise.

Focusable source order is: skip link, request field, work-mode radios, conditional path field,
search checkbox, primary action, approval actions, evidence disclosure, status refresh, then
recent-run buttons. Radio, checkbox, and button focus states use a three-pixel visible outline. The
active job ID and pending approval ID are retained in session storage so a same-tab reload can
resume the appropriate state.

## Visual review

| Dimension | Score | Evidence |
|---|---:|---|
| Task-flow clarity | 5 | The numbered request, result, and status sequence reveals the complete task on the first screen. |
| Information architecture | 5 | Request and result own the wide column; health and history remain in a 340px subordinate rail. |
| Typographic consistency | 4 | Repeated heading and metadata roles are consistent; final rendering still depends on installed system Korean fonts. |
| Spacing and alignment consistency | 5 | All repeated gaps use the documented 4/8/12/16/24/32 scale and shared column edges. |
| Reasoned visual variation | 5 | Green, amber, and red appear only for action, health/verification, attention, and failure. |
| Primary-content readability | 5 | The 11,986-character result stays at a 780px measure with 1.75 line height and wrapping code blocks. |
| Component consistency | 4 | Controls share border, radius, and focus rules; native checkbox rendering varies by browser. |
| Functional discoverability | 5 | Read-only and file-change modes are distinct; the second approval step makes the write boundary explicit before execution. |
| Whole-screen coherence | 5 | One border system, one radius family, restrained status backgrounds, and no decorative shadows unify the screen. |
| Robustness and accessibility | 5 | Zero console errors, no tested overflow, visible focus, semantic regions, live status, approval/error/rollback states, and mobile stacking rules. |

Overall judgment: strong for the local read-and-scoped-write MVP. No must-pass dimension is below 4.

## Remaining uncertainties

- Chrome path discovery is unit-tested, but automated interaction QA used the connected in-app
  browser. The launch command still explicitly selects Chrome.
- The connected browser exposed a fixed 1280×720 viewport for this pass. The exact 1440×900,
  1920×1080, and 390×844 captures validate the shared shell baseline; the newly added approval card
  was interactively checked only at 1280×720.
- Jobs live in server memory. A server restart, unlike a page reload, loses the active job handle;
  completed run artifacts and approval evidence still remain under `runs/`.
- Rollback verifies the complete pre-execution file snapshot but does not track empty directories.
- Backup v2 stores one verified content-addressed blob per unique file value inside each run,
  including Git-ignored inputs. It still hashes the full snapshot and does not reuse blobs across
  runs, so very large repositories will need a cross-run incremental store.
