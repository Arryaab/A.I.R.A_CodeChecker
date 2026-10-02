from solution import pairwise_euclidean

def test_triangle_distances():
    pts = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    d = pairwise_euclidean(pts)
    assert d[1][2] == d[2][1]
