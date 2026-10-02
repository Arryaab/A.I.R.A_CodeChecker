from solution import pkcs7_unpad

def test_valid_pkcs7_unpad():
    data = b"secret data" + bytes([5] * 5)
    assert pkcs7_unpad(data, 16) == b"secret data"
