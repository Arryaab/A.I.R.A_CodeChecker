import pytest
from solution import pack_binary_frames

def test_small_frames():
    frames = [b"\x01\x02", b"\x03\x04"]
    assert pack_binary_frames(frames) == b"\x01\x02\x03\x04"
