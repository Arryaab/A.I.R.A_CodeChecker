import pytest
from solution import LRUCache

def test_oracle_lru_access_sequence():
    c = LRUCache(3)
    for k in ["1", "2", "3"]:
        c.put(k, k)
    c.get("1")
    c.get("2")
    c.put("4", "4")  # evicts "3"
    assert c.get("3") is None
    assert c.get("1") == "1"
    assert c.get("2") == "2"
    assert c.get("4") == "4"
