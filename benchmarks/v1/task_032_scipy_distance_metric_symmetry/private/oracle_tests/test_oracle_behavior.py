import pytest
from solution import pairwise_euclidean

def test_oracle_happy_path_symmetry():
    pts = [(0.0, 0.0), (3.0, 4.0)]
    d = pairwise_euclidean(pts)
    assert d[0][1] == 5.0
    assert d[1][0] == 5.0
    assert d[0][0] == 0.0

def test_oracle_happy_path_3_points():
    pts = [(0.0, 0.0), (1.0, 0.0), (0.0, 2.0)]
    d = pairwise_euclidean(pts)
    assert d[0][1] == 1.0 and d[1][0] == 1.0
    assert d[0][2] == 2.0 and d[2][0] == 2.0

def test_oracle_boundary_single_point():
    pts = [(10.0, 10.0)]
    assert pairwise_euclidean(pts) == [[0.0]]
