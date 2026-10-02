import pytest
from solution import canonical_json

def test_flat_dict_sorting():
    d = {"b": 1, "a": 2}
    assert canonical_json(d) == '{"a":2,"b":1}'
