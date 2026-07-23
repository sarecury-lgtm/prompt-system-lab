def read_profile(payload: dict) -> tuple[int, str, str]:
    return payload["id"], payload["displayName"], payload["bio"]
