import pytest
from solution import format_log_entry

def test_oracle_default_uninitialized_context():
    # Fresh execution without setting contextvar
    entry = format_log_entry("ERROR", "Unhandled error")
    assert "[ERROR]" in entry
    assert "[req:-]" in entry
