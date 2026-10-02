import pytest
from solution import GenericEnvelope

def test_oracle_happy_path_valid_int_items():
    env = GenericEnvelope(int)
    res = env.parse({"items": [1, 2, 3]})
    assert res == {"count": 3, "items": [1, 2, 3]}

def test_oracle_boundary_empty_items():
    env = GenericEnvelope(str)
    res = env.parse({"items": []})
    assert res == {"count": 0, "items": []}

def test_oracle_negative_invalid_type_raises():
    env = GenericEnvelope(int)
    with pytest.raises(TypeError, match="is not of type int"):
        env.parse({"items": [1, "two", 3]})

def test_oracle_negative_empty_payload():
    env = GenericEnvelope(str)
    res = env.parse({})
    assert res == {"count": 0, "items": []}
