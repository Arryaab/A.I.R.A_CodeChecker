import pytest
from solution import match_choice

def test_case_sensitive_strict():
    choices = ["Fast", "Standard"]
    with pytest.raises(ValueError):
        match_choice("fast", choices, case_sensitive=True)
