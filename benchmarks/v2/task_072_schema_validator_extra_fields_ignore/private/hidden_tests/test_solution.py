import pytest
from solution import validate_user_payload

def test_extra_metadata_accepted():
    data = {
        "username": "john",
        "email": "john@example.com",
        "role": "admin",
        "extra_info": {"custom": 123}
    }
    # Should NOT raise ValidationError
    res = validate_user_payload(data)
    assert res["username"] == "john"
