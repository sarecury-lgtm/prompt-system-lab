from app.auth import hash_password, login


def test_valid_login_succeeds():
    users = {"user@example.com": hash_password("secret")}
    assert login("user@example.com", "secret", users)


def test_wrong_password_fails():
    users = {"user@example.com": hash_password("secret")}
    assert not login("user@example.com", "wrong", users)
