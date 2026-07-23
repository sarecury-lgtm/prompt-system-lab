from app.payment import charge


class FakeGateway:
    def charge(self, amount: int, api_key: str) -> str:
        assert api_key == "test-key"
        return f"ok:{amount}"


def test_charge_with_fake_gateway(monkeypatch):
    monkeypatch.setenv("PAYMENT_API_KEY", "test-key")
    assert charge(1200, FakeGateway()) == "ok:1200"
