import pytest
from solution import format_log_entry, request_id_var

def test_log_entry_without_request_id():
    token = request_id_var.set(None)
    try:
        entry = format_log_entry("WARN", "No context present")
        assert "[req:-]" in entry
    finally:
        request_id_var.reset(token)
