def validate_user_payload(data: dict) -> dict:
    # BUG: creates a copy but forgets to include original fields
    if "first_name" in data and "last_name" in data:
        return {"full_name": f"{data['first_name']} {data['last_name']}"}
    return data
