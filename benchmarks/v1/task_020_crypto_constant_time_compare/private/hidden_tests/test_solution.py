from solution import constant_time_compare

def test_different_lengths():
    assert constant_time_compare(b"short", b"longer_string") is False
