import pytest
from solution import pkcs7_unpad

def test_corrupt_padding_rejected():
    corrupt = b"message" + b"\x00" * 7 + b"\x02\x03"
    with pytest.raises(ValueError):
        pkcs7_unpad(corrupt, block_size=16)
