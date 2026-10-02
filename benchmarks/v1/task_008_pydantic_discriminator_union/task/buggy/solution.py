def parse_event(data: dict):
    # BUG: missing discriminator check raises generic KeyError or parses wrong model
    event_type = data.get("type")
    if event_type == "click":
        return {"kind": "click", "x": data["x"], "y": data["y"]}
    elif event_type == "hover":
        return {"kind": "hover", "duration": data["duration"]}
    # Forgot to raise ValueError for unknown discriminator
    return data
