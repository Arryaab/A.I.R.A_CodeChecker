import pytest
from solution import OK, NOT_FOUND

def test_integer_comparison_backward_compat():
    assert OK == 200
    assert NOT_FOUND == 404
    assert OK != 404

def test_int_conversion():
    assert int(OK) == 200
    assert OK < 300
