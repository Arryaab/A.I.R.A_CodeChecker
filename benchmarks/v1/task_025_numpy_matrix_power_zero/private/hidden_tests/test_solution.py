from solution import matrix_power

def test_matrix_power_one_and_two():
    m = [[1.0, 1.0], [1.0, 0.0]]
    assert matrix_power(m, 1) == m
    assert matrix_power(m, 2) == [[2.0, 1.0], [1.0, 1.0]]
