import pytest
from solution import parse_asn1_length

def test_oracle_happy_path_short_form():
    length, next_offset = parse_asn1_length(bytes([0x2A, 0x01]), offset=0)
    assert length == 42
    assert next_offset == 1

def test_oracle_happy_path_long_form():
    data = bytes([0x82, 0x01, 0x00, 0xAA])
    length, next_offset = parse_asn1_length(data, offset=0)
    assert length == 256
    assert next_offset == 3

def test_oracle_negative_truncated_length():
    with pytest.raises(ValueError, match="Truncated ASN.1 length header"):
        parse_asn1_length(bytes([0x82, 0x01]), offset=0)

def test_oracle_negative_eof():
    with pytest.raises(ValueError, match="Unexpected EOF"):
        parse_asn1_length(b"", offset=0)
