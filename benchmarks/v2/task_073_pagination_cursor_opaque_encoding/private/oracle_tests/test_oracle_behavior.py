import pytest
from solution import decode_cursor

def test_oracle_empty_token_zero():
    assert decode_cursor("") == 0
