# Python Login Bug Fixture

Purpose: provide one reproducible repository-level case for CODE-NORMAL-01.

## Initial failure

```text
1 failed, 1 passed
FAILED tests/test_auth.py::test_valid_login_succeeds
```

The stored password uses `hexdigest()` and is a string, while `verify_password()` compares it with `digest()` bytes.

## Minimal repair

Replace only:

```python
hashlib.sha256(password.encode()).digest() == stored_hash
```

with:

```python
hashlib.sha256(password.encode()).hexdigest() == stored_hash
```

## Validation observed locally

```text
2 passed in 0.02s
```

This fixture is intentionally small. It tests whether a prompt causes the coding agent to inspect the failing test, identify the type/representation mismatch, make one local change, and report actual test results instead of rewriting the authentication flow.
