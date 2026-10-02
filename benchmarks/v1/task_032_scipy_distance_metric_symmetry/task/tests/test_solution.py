from solution import pairwise_euclidean

def test_distance_matrix_symmetry():
    pts = [(0.0, 0.0), (3.0, 4.0)]
    d = pairwise_euclidean(pts)
    assert d[0][1] == 5.0
    assert d[1][0] == 5.0
    assert d[0][0] == 0.0
