# Multifile Profile Contract Fixture

Case: `CODE-LONG-05`.

Initial local result:

```text
2 failed
```

Failures:

1. Backend serializes `display_name`, while the frontend reads `displayName`.
2. The API includes `bio`, but the migration does not define a `bio` column.

Exploratory variant results:

| Variant | Result | Main behavior |
|---|---|---|
| A | 1 passed, 1 failed | fixed the immediate frontend key only; left migration incomplete |
| B | 2 passed | fixed backend contract and migration, but added an unused compatibility helper |
| C | 2 passed | followed the cross-file contract and changed backend plus migration |
| D | 2 passed | same successful scope as C, explicitly driven by entrypoint/dependency/contract checks |

This fixture is deliberately small but cross-file. It tests whether the prompt prevents a locally plausible one-file repair from being mistaken for a complete service repair.