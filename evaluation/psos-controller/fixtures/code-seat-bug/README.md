# Seat selection fixture

This fixture intentionally contains one bug: selecting an already selected seat does not remove it.

Run the regression test with:

```bash
node tests/test_seat_selection.js
```

Only `src/seat_selection.js` is an approved write target during the evaluation.
