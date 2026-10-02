import pytest
from solution import extract_log_severities

def test_basic_extraction():
    lines = ["[INFO] Started worker", "Malformed line", "[ERROR] Connection lost"]
    assert extract_log_severities(lines) == ["INFO", "ERROR"]
