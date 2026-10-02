import pytest
from solution import align_multiindex_data

def test_oracle_happy_path_outer_join():
    d1 = {("A", 1): 10}
    d2 = {("B", 2): 20}
    res = align_multiindex_data(d1, d2)
    assert res == {("A", 1): 10, ("B", 2): 20}

def test_oracle_happy_path_sum_overlapping():
    d1 = {("A", 1): 5, ("A", 2): 10}
    d2 = {("A", 2): 15, ("C", 1): 20}
    res = align_multiindex_data(d1, d2)
    assert res[("A", 1)] == 5
    assert res[("A", 2)] == 25
    assert res[("C", 1)] == 20

def test_oracle_boundary_one_empty():
    d1 = {("X", 1): 100}
    assert align_multiindex_data(d1, {}) == {("X", 1): 100}
