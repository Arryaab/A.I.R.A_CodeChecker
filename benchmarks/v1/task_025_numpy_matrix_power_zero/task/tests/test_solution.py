from solution import matrix_power

def test_matrix_power_zero_returns_identity():
    m = [[2.0, 3.0], [4.0, 5.0]]
    expected = [[1.0, 0.0], [0.0, 1.0]]
    assert matrix_power(m, 0) == expected
