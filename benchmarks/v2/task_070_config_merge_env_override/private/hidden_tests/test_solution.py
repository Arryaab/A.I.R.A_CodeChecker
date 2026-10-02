import pytest
from solution import merge_configs

def test_nested_dictionary_retention():
    base = {
        "db": {"host": "localhost", "port": 5432, "timeout": 30}
    }
    override = {
        "db": {"port": 5433}
    }
    res = merge_configs(base, override)
    # Port is updated
    assert res["db"]["port"] == 5433
    # Host and timeout MUST NOT be wiped out
    assert res["db"]["host"] == "localhost"
    assert res["db"]["timeout"] == 30
