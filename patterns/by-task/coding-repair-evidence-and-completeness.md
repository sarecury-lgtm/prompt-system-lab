# Candidate Pattern — Coding Repair Evidence and Completeness

Status: exploratory candidate; not runtime-promoted.

Evidence:

- Source candidates: PR088 and PR093
- Fixtures: `python-login-bug`, `ambiguous-test-bug`, `payment-production-unknown`, `docs-injection-bug`, `multifile-profile-contract`
- Pilot: `2026-07-23-code-exploratory`

## Part 1 — Evidence before edit

```text
Inspect and attempt to reproduce or isolate the failure before editing. If the available repository, tests, logs, or environment evidence does not support a code cause, report the validation result, avoid speculative changes, and request the smallest missing diagnostics.
```

This rule is especially important for reported production incidents that pass locally.

## Part 2 — Smallest complete change

```text
Minimize scope, but follow entrypoints, imports, API/type contracts, configuration, and migrations far enough to make the repair complete. Validate every affected contract, not only the first failing file.
```

## Trigger

Apply Part 1 whenever the failure is not already reproduced. Apply Part 2 when multiple files, services, schemas, configurations, or migrations participate in the failing flow.

## Do not apply heavily

- one-line or single-function failures already isolated by a clear test
- explanation-only code questions
- tasks where repository or execution tools are unavailable

## Main risks

- `smallest change` becoming an incomplete one-file patch
- generic robustness additions that alter unrelated behavior
- claiming a production fix from passing local tests
- applying a full repository workflow to a trivial isolated failure
