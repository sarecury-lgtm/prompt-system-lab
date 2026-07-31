# Corpus Registry Core

The repository keeps the broad PR001–PR130 source corpus separate from the narrow runtime and approved-prompt layers.

## Included layer

- `corpus/registry.csv`: one row for every PR001–PR130 entry
- `corpus/CORPUS_STATUS_POLICY.md`: evidence requirements and promotion boundaries
- `scripts/validate_corpus_registry.py`: deterministic range, duplicate, and registry validation
- `.github/workflows/corpus-registry-validation.yml`: pull-request and `main` regression check

The initial registry is deliberately conservative: 10 entries are `reviewed`, 4 are `recovered`, and 116 remain `raw`. These labels describe repository evidence only. They do not prove that an external source is authentic or effective.

## Runtime boundary

The full corpus is not automatically searched or applied. A source entry may inform a new candidate, but runtime or approved-baseline promotion still requires applied comparison evidence under the current validation process.

## Excluded from the old restoration branch

The old PR #42 also contained dated exploratory argument, product, and coding runs; blind-review drafts; task-specific candidate patterns; fixtures; and synthesis reports. Those artifacts were not moved into this core layer because later approved-baseline and applied-patch reviews supersede their promotion path.

Nothing in this core layer changes the canonical runtime, approved prompt registry, or current product-prompt decision.
