import hashlib


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    # Intentional fixture bug: bytes/string mismatch after a hash-library style change.
    return hashlib.sha256(password.encode()).digest() == stored_hash


def login(email: str, password: str, users: dict[str, str]) -> bool:
    stored = users.get(email)
    return stored is not None and verify_password(password, stored)
