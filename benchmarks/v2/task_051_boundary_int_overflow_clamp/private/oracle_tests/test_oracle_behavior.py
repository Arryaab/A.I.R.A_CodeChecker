import pytest
from solution import clamp_range

def test_oracle_boundary_invariants():
    for bound in [-100, -1, 0, 1, 100]:
        assert clamp_range(bound, bound, bound) == bound
        assert clamp_range(bound - 1, bound, bound + 10) == bound
        assert clamp_range(bound + 10, bound, bound + 10) == bound + 10
        assert clamp_range(bound + 11, bound, bound + 10) == bound + 10
