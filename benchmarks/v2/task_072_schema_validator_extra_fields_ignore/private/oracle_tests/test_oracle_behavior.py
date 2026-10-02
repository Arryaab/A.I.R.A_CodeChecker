import pytest
from solution import validate_user_payload, ValidationError

def test_oracle_data_integrity():
    with pytest.raises(ValidationError):
        validate_user_payload({"username": "", "email": "a@b.com"})
    with pytest.raises(ValidationError):
        validate_user_payload({"username": "valid", "email": "invalid_email"})
