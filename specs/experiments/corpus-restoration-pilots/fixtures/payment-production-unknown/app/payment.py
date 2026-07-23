import os


class GatewayError(RuntimeError):
    pass


def charge(amount: int, gateway) -> str:
    api_key = os.getenv("PAYMENT_API_KEY")
    if not api_key:
        raise GatewayError("payment gateway is not configured")
    return gateway.charge(amount=amount, api_key=api_key)
