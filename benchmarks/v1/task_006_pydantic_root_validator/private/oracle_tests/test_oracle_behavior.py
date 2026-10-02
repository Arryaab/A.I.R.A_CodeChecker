import pytest
from solution import validate_user_payload

def test_oracle_happy_path_combine_and_preserve():
    payload = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "role": "mathematician",
        "id": 42
    }
    result = validate_user_payload(payload)
    assert result["full_name"] == "Ada Lovelace"
    assert result["first_name"] == "Ada"
    assert result["last_name"] == "Lovelace"
    assert result["email"] == "ada@example.com"
    assert result["role"] == "mathematician"
    assert result["id"] == 42

def test_oracle_boundary_only_first_name():
    payload = {"first_name": "Ada", "email": "ada@example.com"}
    result = validate_user_payload(payload)
    assert "full_name" not in result
    assert result["first_name"] == "Ada"

def test_oracle_boundary_neither_name():
    payload = {"role": "guest", "id": 10}
    assert validate_user_payload(payload) == {"role": "guest", "id": 10}

def test_oracle_regression_input_immutability():
    original = {"first_name": "Alan", "last_name": "Turing", "dept": "CS"}
    result = validate_user_payload(original)
    assert result["dept"] == "CS"
    assert result["full_name"] == "Alan Turing"
