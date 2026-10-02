import pytest
from solution import truncate_token_pair

def test_oracle_happy_path_truncates_preserving_special():
    a = ["w1", "w2", "w3"]
    b = ["w4", "w5"]
    res = truncate_token_pair(a, b, max_length=6)
    assert res[0] == "[CLS]"
    assert res[-1] == "[SEP]"
    assert len(res) == 6

def test_oracle_boundary_no_truncation_needed():
    a = ["w1"]
    b = ["w2"]
    res = truncate_token_pair(a, b, max_length=10)
    assert res == ["[CLS]", "w1", "[SEP]", "w2", "[SEP]"]

def test_oracle_negative_max_length_too_short():
    with pytest.raises(ValueError, match="max_length too short"):
        truncate_token_pair(["a"], ["b"], max_length=2)
