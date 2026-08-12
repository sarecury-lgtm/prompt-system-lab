# PSOS Controller A/B evaluation report

Status: **prepared; no live Codex run yet**

## Pre-registered scope

- DIRECT: supplied argument analysis without web research
- RESEARCH: current Python version decision using live sources
- CODE: isolated seat-selection bug fix with one approved write target
- REUSE: inspect and decide whether to reuse an existing claim-extraction tool

## Order of operations

1. Validate and prepare all four cases without model calls.
2. Run only the two pilot cases by default.
3. Review `blind_review_packet.json` before opening `arm_key.json` or `metrics.json`.
4. Save `blind_review_response.json`.
5. Generate the final report, then inspect quality, routing, time and model-call cost together.

## Pre-registered stop conditions

Stop before the two follow-up cases when any of these occurs:

- The Controller adds model calls without improving blind quality.
- Either arm loses a must-preserve condition.
- The Controller repeats the same method instead of changing one material dimension.
- A pre-registered critical failure appears in a pilot case.

## Blind quality result

Pending.

## Unblinded cost and routing result

Pending.

## Promotion decision

A two-case pilot cannot justify CORE promotion. Four distinct reviewed domains are necessary, and promotion still requires separate explicit user approval.
