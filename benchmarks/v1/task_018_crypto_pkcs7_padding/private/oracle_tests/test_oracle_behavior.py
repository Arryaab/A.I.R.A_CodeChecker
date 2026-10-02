import pytest
from solution import pkcs7_unpad

def test_oracle_happy_path_valid():
    data = b"message" + b"\x09" * 9
    assert pkcs7_unpad(data, block_size=16) == b"message"

def test_oracle_boundary_full_block_padding():
    data = b"1234567890123456" + b"\x10" * 16
    assert pkcs7_unpad(data, block_size=16) == b"1234567890123456"

def test_oracle_negative_corrupt_padding_byte():
    corrupt = b"message" + b"\x00" * 7 + b"\x02\x03"
    with pytest.raises(ValueError):
        pkcs7_unpad(corrupt, block_size=16)

def test_oracle_negative_invalid_block_length():
    with pytest.raises(ValueError, match="Invalid block length"):
        pkcs7_unpad(b"short", block_size=16)
