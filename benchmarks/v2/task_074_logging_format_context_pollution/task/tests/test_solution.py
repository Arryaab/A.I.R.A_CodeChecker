import pytest
from solution import format_log_entry, request_id_var

def test_log_entry_with_request_id():
    token = request_id_var.set("req_123")
    try:
        entry = format_log_entry("INFO", "Operation succeeded")
        assert "[req:REQ_123]" in entry
    finally:
        request_id_var.reset(token)
