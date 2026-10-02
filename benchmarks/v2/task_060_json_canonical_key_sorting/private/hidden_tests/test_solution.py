import pytest
from solution import canonical_json

def test_nested_dict_sorting():
    d = {"z": {"b": 2, "a": 1}, "a": [3, 2, 1]}
    assert canonical_json(d) == '{"a":[3,2,1],"z":{"a":1,"b":2}}'

def test_dicts_inside_lists():
    d = [{"k2": "v2", "k1": "v1"}]
    assert canonical_json(d) == '[{"k1":"v1","k2":"v2"}]'
