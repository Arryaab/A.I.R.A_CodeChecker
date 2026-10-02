import pytest
from solution import match_choice

def test_oracle_happy_path_case_insensitive():
    choices = ["Fast", "Standard", "Deep"]
    assert match_choice("fast", choices, case_sensitive=False) == "Fast"
    assert match_choice("STANDARD", choices, case_sensitive=False) == "Standard"

def test_oracle_happy_path_case_sensitive():
    choices = ["Fast", "fast"]
    assert match_choice("Fast", choices, case_sensitive=True) == "Fast"
    assert match_choice("fast", choices, case_sensitive=True) == "fast"

def test_oracle_negative_case_sensitive_mismatch():
    choices = ["Fast", "Deep"]
    with pytest.raises(ValueError):
        match_choice("fast", choices, case_sensitive=True)

def test_oracle_negative_invalid_choice():
    with pytest.raises(ValueError):
        match_choice("unknown", ["A", "B"], case_sensitive=False)
