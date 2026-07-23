# Exploratory Summary — Coding Repair

## Verdict

The current Compiler did not improve every coding repair. Its value appeared only at two boundaries:

1. do not edit when the failure is not reproduced or evidenced
2. trace cross-file contracts when a one-file repair can leave the system incomplete

Provisional means out of 14 across four cases:

| Variant | Mean |
|---|---:|
| A — minimal baseline | 12.5 |
| B — generic improver | 8.75 |
| C — current Compiler | 13.0 |
| D — bounded source candidate | 13.5 |

This is same-session, unblinded, and not promotion-eligible.

## Case boundaries

### Simple observable failure

For the ambiguous slug test and clearly labeled injection case, baseline was already sufficient. C/D added process language but no substantive gain.

### Production incident without reproduction

The most important coding behavior was not `inspect → edit → test`; it was:

```text
inspect → attempt reproduction → if evidence is insufficient, do not edit → collect the smallest missing diagnostics
```

This boundary should be part of the coding task pattern.

### Cross-file completeness

The multifile fixture showed a real difference. A locally plausible frontend-only patch left one test failing. C/D followed the API and migration contract and completed the repair. D's PR093 mechanism was the clearest explanation of why the second file had to change.

## Negative lessons

- Passing visible tests does not excuse unrelated behavior changes.
- Generic “make it robust” additions created hidden regression risk in two easy cases.
- An explicit prompt-injection rule showed no unique gain when the case already labeled the text as untrusted.
- “Smallest change” alone can be wrong when the smallest complete change spans multiple files.

## Pattern decision

Do not promote the whole coding-agent workflow as a universal default from this run. Split it into narrower task mechanisms:

### Evidence-before-edit

```text
Before editing, reproduce or isolate the failure. If available evidence does not support a code cause, report the validation result, avoid speculative changes, and request the smallest missing diagnostics.
```

### Smallest complete change

```text
Minimize scope, but follow entrypoints, imports, API/type contracts, configuration, and migrations far enough to make the repair complete. Validate every affected contract, not only the first failing file.
```

PR093 remains a strong candidate for a task-specific cross-file coding card. PR088 remains useful as a bounded workflow source but did not beat baseline on simple failures.
