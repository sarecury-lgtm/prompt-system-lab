# PSOS local UI QA report

## Deterministic browser checks

Tested against the live local server and real run data.

| Check | 1440×900 | 1920×1080 | 390×844 |
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

The end-to-end form check submitted a real read-only request through the browser. The job entered a
visible running state, completed through `REUSE`, displayed the exact Chrome command, exposed one
evidence item and one inspected artifact, re-enabled the submit control, and refreshed status from
17/17 to 18/18 valid runs.

Focusable source order is: skip link, request field, search checkbox, primary action, evidence
disclosure, status refresh, then recent-run buttons. Checkbox and button focus states showed a
three-pixel visible outline. The active job ID is retained in session storage so a same-tab reload
can resume polling.

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
| Functional discoverability | 4 | The core action and evidence disclosure are clear; policy review remains intentionally outside this safe read-only MVP. |
| Whole-screen coherence | 5 | One border system, one radius family, restrained status backgrounds, and no decorative shadows unify the screen. |
| Robustness and accessibility | 5 | Zero console errors, no tested overflow, visible focus, semantic regions, live status, loading/error states, and mobile stacking. |

Overall judgment: strong for the scoped read-only local MVP. No must-pass dimension is below 4.

## Remaining uncertainties

- Chrome path discovery is unit-tested, but automated QA used the in-app browser to avoid opening a
  visible desktop window during development.
- Jobs live in server memory. A server restart, unlike a page reload, loses the active job handle;
  completed run artifacts still remain under `runs/`.
- Workspace-write requests are deliberately blocked. A future editing UI needs a separate,
  explicit approval and receipt flow rather than a toggle added to this screen.
