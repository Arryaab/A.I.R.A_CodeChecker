import pytest
from solution import has_required_permissions

def test_permissions_met():
    assert has_required_permissions(["read", "write", "admin"], ["read", "write"]) is True

def test_permissions_missing():
    assert has_required_permissions(["read"], ["write"]) is False
