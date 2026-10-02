import pytest
from solution import decode_cursor

def test_legacy_integer_offset_string():
    assert decode_cursor("50") == 50
    assert decode_cursor("0") == 0

def test_invalid_cursor_raises():
    with pytest.raises(ValueError):
        decode_cursor("invalid_payload_!@#$")
