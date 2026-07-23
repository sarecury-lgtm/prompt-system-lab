# Blind Review Workflow

## Purpose

Collect Kare Notes on output quality without revealing A/B/C/D labels during judgment.

## Argument family

The argument run contains full executed outputs and is ready for a blind pack.

```bash
python scripts/build_blind_review_pack.py \
  specs/experiments/corpus-restoration-pilots/runs/2026-07-22-arg-exploratory/outputs.md \
  reviews/generated/argument-blind-pack.md \
  reviews/generated/argument-mapping.csv
```

Review `argument-blind-pack.md` first. Do not open `argument-mapping.csv` until all notes are complete.

## Product and coding families

The current product and coding continuation files contain source ledgers, patch/test results, and same-session output summaries. They are useful exploratory evidence but are not a proper blind-review corpus.

Before verification-level judgment:

1. generate the A/B/C/D prompts from the saved contracts
2. execute them through an independent model/session with identical tools and context
3. save full outputs, commands, diffs, and test results
4. generate a blind pack from the full outputs
5. collect Kare Notes before opening the mapping

## Judgment rule

Judge final task output, not prompt length or professional appearance.

Prefer the shortest output that:

- preserves the actual request and constraints
- avoids unsupported facts or fake execution
- changes the decision or catches a real failure
- does not add structure with no substantive contribution

Use `reviews/kare-notes-template.csv` for recording decisions.
