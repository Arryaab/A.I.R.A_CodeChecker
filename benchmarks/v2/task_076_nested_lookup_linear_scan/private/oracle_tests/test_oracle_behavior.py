import pytest
from solution import has_required_permissions

def test_oracle_empty_requirements():
    assert has_required_permissions([], []) is True
    assert has_required_permissions(["admin"], []) is True
    assert has_required_permissions([], ["admin"]) is False
