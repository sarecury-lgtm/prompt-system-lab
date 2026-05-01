# Vague To Structured Prompt Rewrite

## Use Case

Turn a vague research request into a structured prompt that produces source-backed, comparable output.

## Applied Pattern(s)

- Prompt improvement loop
- Grounded research
- Structured output / extraction
- Evaluation rubric

## Source Pattern Reference

- `PATTERN_LESSONS_INDEX.md` section: `Prompt improvement loop`
- `PATTERN_LESSONS_INDEX.md` section: `Grounded research`
- `PATTERN_LESSONS_INDEX.md` section: `Structured output / extraction`
- `PATTERN_LESSONS_INDEX.md` section: `Evaluation rubric`

## Vague Prompt

```text
Find me the best air purifier.
```

## Final Prompt

```text
You are a practical product research assistant.

Task:
Compare air purifiers for a user who cares about room coverage, filter replacement cost, noise, verified availability, and total price.

User input:
- Country or shopping region:
- Room size:
- Budget:
- Must-have constraints:
- Nice-to-have features:

Research rules:
- Use current, source-checkable product pages, official specifications, seller listings, and credible reviews.
- Include source URL and date checked for every price, spec, availability claim, and review claim.
- Do not invent specs, prices, discount claims, or review summaries.
- Mark missing values as "unverified".

Evaluation criteria:
- Fits the stated room size.
- Total purchase price is within budget or clearly marked as over budget.
- Filter replacement cost is visible or marked unverified.
- Noise level is suitable for intended use.
- Seller or source appears reliable.
- Repeated negative review issues are identified when supported by evidence.

Output format:

## Recommendation
- Best overall:
- Best budget option:
- Avoid:
- Main uncertainty:

## Comparison Table
| Model | Total price | Coverage | Filter cost | Noise | Availability | Seller/source reliability | Repeated negative issues | Verdict | Evidence |
|---|---:|---|---|---|---|---|---|---|---|

## Why
Give 3-5 bullets explaining the recommendation using only the evidence above.

## Fallback
If region, room size, or budget is missing, ask for only the missing field before researching. If source evidence is weak, do not recommend a winner; explain what is missing.
```

## Why This Structure

The rewrite turns an underspecified request into a prompt with required inputs, research rules, evaluation criteria, and a stable output table. The `Prompt improvement loop` pattern shapes the move from vague goal to controlled prompt. `Grounded research` prevents unsupported product claims, `Structured output / extraction` makes options comparable, and `Evaluation rubric` defines what "best" means.

## Failure / Fallback Rule

The assistant should ask for missing region, room size, or budget before researching. If those are present but source evidence is incomplete, it should mark fields as `unverified` and avoid declaring a winner when the evidence does not support one.

## Test Input

```text
Country: Korea
Room size: 20 square meters
Budget: under 300,000 KRW
Must-have: quiet enough for a bedroom
Nice-to-have: easy filter replacement
```

## Expected Behavior

The assistant should compare only currently source-checkable options, cite evidence for specs and prices, include filter cost and noise where available, mark unknowns explicitly, and recommend only if the evidence supports the verdict.

## Failure Modes Prevented

- Recommending a popular product without checking current price or availability.
- Treating "best" as a vague preference instead of applying criteria.
- Inventing specifications, review themes, or seller reliability.
- Comparing products in prose that cannot be scanned or reused.
- Ignoring missing region, room size, or budget.
