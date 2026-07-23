def serialize_profile(row: dict) -> dict:
    return {
        "id": row["id"],
        "display_name": row["display_name"],
        "bio": row.get("bio", ""),
    }
