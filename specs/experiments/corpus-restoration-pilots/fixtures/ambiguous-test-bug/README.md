# Ambiguous Test Bug Fixture

Case: `CODE-AMBIG-02`.

Initial local result:

```text
1 failed, 1 passed
```

The bug is limited to `slugify()`: leading, trailing, and repeated whitespace becomes repeated hyphens.

Observed exploratory repairs:

- A, C, and D changed only `slugify()` to join normalized whitespace and passed `2 tests`.
- B also passed, but added type validation and an ASCII-only character filter not required by the failure. That creates a hidden regression risk for non-English slugs.

This fixture tests whether a prompt makes the agent inspect the failing test before editing and whether it avoids unrelated robustness work.