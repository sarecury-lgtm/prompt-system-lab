from pathlib import Path

from backend.profile import serialize_profile
from frontend.profile import read_profile


def test_backend_frontend_profile_contract():
    payload = serialize_profile({"id": 1, "display_name": "Kare", "bio": "hello"})
    assert read_profile(payload) == (1, "Kare", "hello")


def test_profile_migration_contains_bio():
    sql = Path("db/001_profiles.sql").read_text()
    assert "bio TEXT" in sql
