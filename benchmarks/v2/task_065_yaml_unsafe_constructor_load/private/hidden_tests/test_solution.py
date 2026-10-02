import pytest
from solution import instantiate_custom_type, SecurityError

def test_unregistered_type_blocked():
    with pytest.raises(SecurityError):
        instantiate_custom_type("SecurityError", {"args": ("test",)})

def test_arbitrary_callable_blocked():
    with pytest.raises(SecurityError):
        instantiate_custom_type("eval", {})
