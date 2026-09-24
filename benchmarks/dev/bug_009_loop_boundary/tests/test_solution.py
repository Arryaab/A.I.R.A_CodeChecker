from solution import fibonacci

def test_fib_pass():
    assert fibonacci(1) == 1

def test_fib_fail():
    assert fibonacci(5) == 5
