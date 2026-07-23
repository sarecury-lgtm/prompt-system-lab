# Exploratory Summary — Product Comparison (partial)

## Scope

This run covers only the three cases that can be judged without inventing live product facts:

- PROD-AMBIG-02 — no models or use case supplied
- PROD-POOR-03 — product families named without generation/configuration/region
- PROD-CONFLICT-04 — mutually demanding constraints without candidates

The two exact-SKU cases remain pending source-backed web execution.

## Variant behavior

### A — minimal baseline

- Correctly refused to invent models or exact prices in all three cases.
- Asked for the missing model/configuration information in the ambiguous cases.
- Identified the conflicting requirements in PROD-CONFLICT-04.
- Weakness: the clarification request was not always organized around the smallest set of facts needed for a fair comparison.

### B — generic prompt improver

- Preserved the no-guessing requirement.
- Added a large checklist of possible comparison dimensions even when the user only asked a short question.
- Often made the future task look more professional without changing the immediate decision: more information was required.

### C — current Prompt Compiler

- Best at converting vague product-family names into an explicit requirement for exact generation, display size, RAM/SSD, region, budget, and use case.
- Best at separating manufacturer claims, independent measurements, and unknown values.
- Weakness: for PROD-AMBIG-02 it still produced more procedure than necessary; a one-batch clarification request would have been sufficient.

### D — PR106/PR109 grounded candidate

- Added the clearest evidence boundary: do not compare product families as if they were one SKU; collect evidence first; distinguish confirmed facts from inference; leave unverifiable fields unknown.
- Its unique gain over C was small on the two missing-information cases.
- On PROD-CONFLICT-04 it stated that the requirement set may have no satisfying option and required the final answer to show which constraint must be relaxed before recommending anything.

## Provisional scores

Maximum: 14 per case. Same model generated and reviewed all outputs; not blinded.

| Variant | Mean | Interpretation |
|---|---:|---|
| A — minimal baseline | 12.7 | already handles missing information and obvious conflicts well |
| B — generic improver | 11.3 | adds breadth but often unnecessary structure |
| C — current Compiler | 13.0 | strongest missing-field contract, but can over-structure a simple clarification |
| D — grounded candidate | 13.3 | clearest evidence and infeasibility boundary; small gain in these three cases |

## Main finding

The Compiler has a more visible advantage here than in short argument analysis, but the advantage is narrow:

> It is useful when product names, configurations, regions, measurement methods, or constraints are easy to mix. It is not useful merely because the request contains the word “compare.”

For a completely unspecified request such as “compare three laptops,” the best response is still a compact clarification request, not a full research protocol.

## Decision

- Do not change the runtime bundle yet.
- Keep grounded research and structured comparison as product-comparison candidates, not proven universal defaults.
- Add a routing boundary: when essential products or configurations are missing, ask for them in one batch before generating the heavy comparison prompt.
- Complete exact-SKU source-backed cases before considering E3.
