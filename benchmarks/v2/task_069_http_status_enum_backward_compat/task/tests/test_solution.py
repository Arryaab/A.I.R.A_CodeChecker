import pytest
from solution import OK, NOT_FOUND

def test_status_representation():
    assert "200" in repr(OK)
    assert "OK" in repr(OK)
