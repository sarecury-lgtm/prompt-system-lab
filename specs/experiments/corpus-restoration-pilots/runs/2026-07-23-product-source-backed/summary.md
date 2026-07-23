# Exploratory Summary — Product Comparison (source-backed)

## Verdict

The current Compiler showed a real but narrow advantage in the two exact-product cases. The advantage was **source validation**, not a larger comparison template.

Provisional mean scores out of 14:

| Variant | Mean |
|---|---:|
| A — minimal baseline | 9.5 |
| B — generic improver | 7.5 |
| C — current Compiler | 12.5 |
| D — grounded candidate | 13.5 |

This run is same-session, unblinded, and not promotion-eligible.

## Unique behaviors that mattered

1. Reject a result whose page content does not match the named product, even when the domain is official.
2. Do not transfer a battery or repair result from a model family to an exact SKU without configuration compatibility.
3. Treat list price, promotion, refurbished, used, and import prices as different facts.
4. Show unresolved conflicts instead of averaging them into a plausible-looking range.
5. Block total-cost ranking when market availability, warranty, or acquisition price is unknown.

## What did not help

- adding more table columns
- giving every field a numerical score
- turning missing values into broad estimates
- treating citations as proof that evidence is compatible

## Pattern decision

Keep `grounded-research` as an E0 general pattern for now. The observed gain should be captured first as a narrower task pattern:

```text
For product comparison, validate exact product identity, configuration, market, date, measurement method, and sale condition before transferring any fact into the comparison. Reject internally mismatched pages. Show conflicting evidence and block rankings that depend on unresolved identity, market, or price facts.
```

Candidate location: `patterns/by-task/product-comparison-source-validation.md`.

Do not change the runtime bundle until a blinded or independent run confirms the gain.
