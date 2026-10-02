import pytest
from solution import parse_asn1_length

def test_truncated_asn1_length_header_raises():
    truncated = bytes([0x82, 0x01])  # specifies 2 octets, but only 1 provided
    with pytest.raises(ValueError):
        parse_asn1_length(truncated, 0)
