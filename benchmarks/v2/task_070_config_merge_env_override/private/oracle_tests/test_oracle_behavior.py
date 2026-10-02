import pytest
from solution import merge_configs

def test_oracle_deep_nesting():
    b = {"a": {"b": {"c": 1, "d": 2}}}
    o = {"a": {"b": {"c": 99}}}
    r = merge_configs(b, o)
    assert r["a"]["b"]["c"] == 99
    assert r["a"]["b"]["d"] == 2
