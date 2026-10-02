import pytest
import time
from solution import validate_alphanumeric_token

def test_redos_adversarial_input_fast():
    # Long non-matching token with invalid character at end
    adversarial = "a" * 28 + "!"
    t0 = time.time()
    res = validate_alphanumeric_token(adversarial)
    elapsed = time.time() - t0
    assert res is False
    assert elapsed < 0.2, f"ReDoS vulnerability: took {elapsed:.2f}s"
