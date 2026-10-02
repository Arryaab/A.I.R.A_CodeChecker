import pytest
from solution import quote_identifier

def test_oracle_quote_invariants():
    for name in ['col', 'a"b', 'a""b', 'test--1']:
        q = quote_identifier(name)
        assert q.startswith('"') and q.endswith('"')
        # Inner quotes must occur in pairs
        inner = q[1:-1]
        assert inner.count('"') % 2 == 0
