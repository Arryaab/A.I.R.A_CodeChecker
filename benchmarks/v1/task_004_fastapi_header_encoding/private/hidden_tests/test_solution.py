from solution import decode_header

def test_utf8_header_standard():
    raw = b"hello world"
    assert decode_header(raw) == "hello world"
