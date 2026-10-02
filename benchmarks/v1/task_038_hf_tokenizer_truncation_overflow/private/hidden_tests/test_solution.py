from solution import truncate_token_pair

def test_no_truncation_needed():
    a = ["hello"]
    b = ["world"]
    res = truncate_token_pair(a, b, max_length=10)
    assert res == ["[CLS]", "hello", "[SEP]", "world", "[SEP]"]
