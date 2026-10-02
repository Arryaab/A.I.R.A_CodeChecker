import pytest
from solution import ConnectionPool

def test_oracle_happy_path_acquire_release():
    pool = ConnectionPool(size=3)
    conn = pool.acquire()
    assert conn == "conn"
    assert pool.available == 2
    pool.release()
    assert pool.available == 3

def test_oracle_negative_double_release_capped():
    pool = ConnectionPool(size=2)
    pool.acquire()
    pool.release()
    pool.release()
    pool.release()
    assert pool.available == 2

def test_oracle_negative_exhausted_pool():
    pool = ConnectionPool(size=1)
    pool.acquire()
    with pytest.raises(RuntimeError, match="Pool exhausted"):
        pool.acquire()
