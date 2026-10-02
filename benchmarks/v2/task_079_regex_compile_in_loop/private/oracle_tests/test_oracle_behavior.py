import pytest
from solution import extract_log_severities

def test_oracle_empty_input():
    assert extract_log_severities([]) == []
