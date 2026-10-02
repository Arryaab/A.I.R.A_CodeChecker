import pytest
from solution import validate_query_param

def test_oracle_happy_path_exact_max_boundary():
    assert validate_query_param("a" * 50, min_length=1, max_length=50) is True

def test_oracle_boundary_min_length():
    assert validate_query_param("a", min_length=1, max_length=50) is True
    assert validate_query_param("", min_length=1, max_length=50) is False

def test_oracle_boundary_max_length_plus_one():
    assert validate_query_param("a" * 51, min_length=1, max_length=50) is False

def test_oracle_regex_pattern_matching():
    pat = r"^[a-z]+_\d+$"
    assert validate_query_param("user_123", min_length=1, max_length=50, pattern=pat) is True
    assert validate_query_param("USER_123", min_length=1, max_length=50, pattern=pat) is False

def test_oracle_invariants_boolean_return():
    assert isinstance(validate_query_param("test"), bool)
