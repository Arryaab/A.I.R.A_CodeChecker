from solution import constant_time_compare

def test_constant_time_compare_equal():
    assert constant_time_compare(b"hash123", b"hash123") is True

def test_constant_time_compare_diff_same_prefix():
    # Both start with 'h' and have same length; buggy returns True
    assert constant_time_compare(b"hash123", b"hash456") is False
