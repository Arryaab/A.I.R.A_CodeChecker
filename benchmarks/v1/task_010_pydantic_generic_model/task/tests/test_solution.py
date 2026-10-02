import pytest
from solution import GenericEnvelope

def test_generic_envelope_valid():
    env = GenericEnvelope(int)
    res = env.parse({"items": [1, 2, 3]})
    assert res == {"count": 3, "items": [1, 2, 3]}

def test_generic_envelope_invalid_type():
    env = GenericEnvelope(int)
    with pytest.raises(TypeError):
        env.parse({"items": [1, "two", 3]})
