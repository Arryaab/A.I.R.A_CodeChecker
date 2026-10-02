import pytest
from solution import canonical_json

def test_oracle_canonical_invariance():
    d1 = {"a": 1, "nested": {"y": 2, "x": 1}}
    d2 = {"nested": {"x": 1, "y": 2}, "a": 1}
    assert canonical_json(d1) == canonical_json(d2)
