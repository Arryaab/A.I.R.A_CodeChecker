import pytest
from solution import instantiate_custom_type, SecurityError

def test_oracle_allowlist_enforcement():
    for dangerous in ["object", "dict", "list", "Exception", "bytearray"]:
        with pytest.raises(SecurityError):
            instantiate_custom_type(dangerous, {})
