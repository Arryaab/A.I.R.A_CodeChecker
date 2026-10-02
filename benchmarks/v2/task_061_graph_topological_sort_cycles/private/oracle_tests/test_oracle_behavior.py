import pytest
from solution import topological_sort, CycleDetectedError

def test_oracle_topological_properties():
    graph = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
    order = topological_sort(graph)
    assert len(order) == 4
    assert order.index("A") < order.index("D")
