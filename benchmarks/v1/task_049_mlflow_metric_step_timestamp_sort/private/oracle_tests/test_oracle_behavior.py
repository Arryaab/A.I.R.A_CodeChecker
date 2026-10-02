import pytest
from solution import sort_metric_history

def test_oracle_happy_path_sorted_by_step():
    m = [{"step": 10, "val": 0.8}, {"step": 2, "val": 0.2}, {"step": 5, "val": 0.5}]
    res = sort_metric_history(m)
    assert [x["step"] for x in res] == [2, 5, 10]

def test_oracle_boundary_already_sorted():
    m = [{"step": 1}, {"step": 2}]
    assert sort_metric_history(m) == m

def test_oracle_boundary_empty():
    assert sort_metric_history([]) == []
