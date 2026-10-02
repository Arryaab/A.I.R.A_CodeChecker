import pytest
from solution import sample_token

def test_oracle_happy_path_greedy_argmax():
    logits = [1.2, 5.8, 3.4]
    assert sample_token(logits, temperature=0.0) == 1

def test_oracle_happy_path_negative_temperature():
    logits = [10.0, 20.0]
    assert sample_token(logits, temperature=-0.5) == 1

def test_oracle_boundary_positive_temperature():
    logits = [0.0, 100.0]
    assert sample_token(logits, temperature=0.5) == 1
