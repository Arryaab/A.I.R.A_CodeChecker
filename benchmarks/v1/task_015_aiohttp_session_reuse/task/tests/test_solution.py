from solution import ConnectionPool

def test_double_release_does_not_exceed_pool_size():
    pool = ConnectionPool(size=5)
    pool.acquire()
    pool.release()
    pool.release()  # spurious release
    assert pool.available == 5
