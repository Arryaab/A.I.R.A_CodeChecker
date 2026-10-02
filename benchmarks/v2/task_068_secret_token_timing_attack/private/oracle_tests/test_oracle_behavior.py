import pytest
from solution import verify_hmac_signature
import hmac

def test_oracle_constant_time_contract():
    # Verify that verify_hmac_signature uses compare_digest under the hood
    import inspect
    import solution
    src = inspect.getsource(solution.verify_hmac_signature)
    assert "compare_digest" in src
