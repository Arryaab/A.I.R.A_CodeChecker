import pytest
from datetime import datetime
from decimal import Decimal
from solution import custom_serializer

def test_oracle_happy_path_decimal():
    res = custom_serializer(Decimal("19.99"))
    assert res == 19.99
    assert isinstance(res, float)

def test_oracle_happy_path_datetime():
    dt = datetime(2026, 9, 27, 10, 0, 0)
    assert custom_serializer(dt) == dt.isoformat()

def test_oracle_regression_primitives_unchanged():
    assert custom_serializer(100) == 100
    assert custom_serializer("hello") == "hello"
    assert custom_serializer(True) is True
    assert custom_serializer(None) is None

def test_oracle_fallback_to_str():
    class CustomObj:
        def __str__(self):
            return "custom_str"
    assert custom_serializer(CustomObj()) == "custom_str"
