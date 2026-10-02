import pytest
from solution import merge_configs

def test_flat_merge():
    base = {"env": "prod", "retries": 3}
    override = {"retries": 5}
    res = merge_configs(base, override)
    assert res["retries"] == 5
    assert res["env"] == "prod"
