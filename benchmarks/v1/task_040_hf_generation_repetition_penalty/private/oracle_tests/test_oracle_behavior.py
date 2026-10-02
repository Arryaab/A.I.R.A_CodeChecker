import pytest
from solution import apply_repetition_penalty

def test_oracle_happy_path_positive_and_negative():
    logits = [2.0, -2.0, 5.0]
    res = apply_repetition_penalty(logits, seen_tokens={0, 1}, penalty=2.0)
    assert res[0] == pytest.approx(1.0)
    assert res[1] == pytest.approx(-4.0)
    assert res[2] == pytest.approx(5.0)

def test_oracle_boundary_no_seen_tokens():
    logits = [1.0, -1.0]
    res = apply_repetition_penalty(logits, seen_tokens=set(), penalty=2.0)
    assert res == logits

def test_oracle_boundary_penalty_one():
    logits = [3.0, -3.0]
    res = apply_repetition_penalty(logits, seen_tokens={0, 1}, penalty=1.0)
    assert res == logits
