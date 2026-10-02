import pytest
from solution import validate_tensor_shape

def test_oracle_happy_path_dynamic_batch_size():
    expected = (-1, 128, 768)
    assert validate_tensor_shape((16, 128, 768), expected) is True
    assert validate_tensor_shape((1, 128, 768), expected) is True

def test_oracle_negative_mismatched_dimension():
    expected = (-1, 128, 768)
    assert validate_tensor_shape((16, 64, 768), expected) is False

def test_oracle_negative_rank_mismatch():
    expected = (-1, 128, 768)
    assert validate_tensor_shape((16, 128), expected) is False
