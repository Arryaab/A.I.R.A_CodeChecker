from solution import decode_header

def test_latin1_header_fallback():
    raw = b"hello \xe9"
    assert decode_header(raw) == "hello \xe9"
