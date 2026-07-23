from app.users import normalize_email


def test_normalize_email_is_case_insensitive():
    assert normalize_email("  User@Example.COM ") == "user@example.com"
