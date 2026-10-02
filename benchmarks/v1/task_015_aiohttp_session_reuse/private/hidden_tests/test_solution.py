import pytest
from solution import ConnectionPool

def test_pool_exhaustion():
    pool = ConnectionPool(size=2)
    pool.acquire()
    pool.acquire()
    with pytest.raises(RuntimeError):
        pool.acquire()
