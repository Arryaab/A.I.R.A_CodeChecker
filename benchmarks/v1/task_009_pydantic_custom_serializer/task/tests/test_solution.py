from decimal import Decimal
from solution import custom_serializer

def test_decimal_serialized_to_float():
    d = Decimal("19.99")
    assert custom_serializer(d) == 19.99
