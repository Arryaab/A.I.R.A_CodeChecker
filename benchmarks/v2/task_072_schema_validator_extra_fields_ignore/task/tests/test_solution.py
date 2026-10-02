import pytest
from solution import validate_user_payload, ValidationError

def test_valid_user():
    data = {"username": "john", "email": "john@example.com"}
    assert validate_user_payload(data) == data

def test_missing_field():
    with pytest.raises(ValidationError):
        validate_user_payload({"username": "john"})
