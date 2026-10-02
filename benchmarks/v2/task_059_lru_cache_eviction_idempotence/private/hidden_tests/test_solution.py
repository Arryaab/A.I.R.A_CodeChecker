import pytest
from solution import LRUCache

def test_get_promotes_to_mru():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    # Access 'a' -> now 'a' is MRU, 'b' is LRU
    assert cache.get("a") == 1
    # Adding 'c' should evict 'b', NOT 'a'
    cache.put("c", 3)
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3
