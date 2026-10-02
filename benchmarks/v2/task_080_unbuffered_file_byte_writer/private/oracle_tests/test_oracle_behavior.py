import pytest
from solution import pack_binary_frames

def test_oracle_empty_frames():
    assert pack_binary_frames([]) == b""
    assert pack_binary_frames([b"", b""]) == b""
