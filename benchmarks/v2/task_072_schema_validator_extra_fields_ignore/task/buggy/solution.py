class ValidationError(Exception):
    pass

def validate_user_payload(data: dict) -> dict:
    """Validates user payload conforming to v1 schema."""
    required_fields = {"username", "email"}
    for f in required_fields:
        if f not in data:
            raise ValidationError(f"Missing required field: {f}")
    
    # BUG: Forbids unknown fields, breaking backward compatibility with v2 clients sending 'tags' or 'metadata'
    allowed_fields = {"username", "email", "age"}
    extra = set(data.keys()) - allowed_fields
    if extra:
        raise ValidationError(f"Unexpected fields: {extra}")
    return data
