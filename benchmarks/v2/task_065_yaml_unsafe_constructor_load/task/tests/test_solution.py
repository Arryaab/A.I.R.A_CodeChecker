import pytest
from solution import instantiate_custom_type, UserProfile

def test_allowed_type():
    obj = instantiate_custom_type("UserProfile", {"name": "Alice"})
    assert isinstance(obj, UserProfile)
    assert obj.name == "Alice"
