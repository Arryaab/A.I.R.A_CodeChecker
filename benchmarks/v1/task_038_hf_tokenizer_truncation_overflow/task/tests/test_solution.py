from solution import truncate_token_pair

def test_special_tokens_preserved_on_truncation():
    a = ["w1", "w2", "w3"]
    b = ["w4", "w5"]
    res = truncate_token_pair(a, b, max_length=6)
    assert res[0] == "[CLS]"
    assert res[-1] == "[SEP]"
    assert len(res) == 6
