import pytest
from solution import decode_header

def test_oracle_happy_path_ascii():
    assert decode_header(b"Content-Type: application/json") == "Content-Type: application/json"

def test_oracle_happy_path_utf8_multibyte():
    val = "café".encode("utf-8")
    assert decode_header(val) == "café"

def test_oracle_boundary_empty_bytes():
    assert decode_header(b"") == ""

def test_oracle_negative_latin1_fallback():
    raw = b"hello \xe9 world \xff"
    res = decode_header(raw)
    assert res == raw.decode("latin-1")

def test_oracle_adversarial_do_not_default_to_latin1_first():
    val = "café".encode("utf-8")
    decoded = decode_header(val)
    assert len(decoded) == 4
    assert decoded == "café"
