import pytest
from solution import topological_sort, CycleDetectedError

def test_linear_dag():
    graph = {"A": ["B"], "B": ["C"], "C": []}
    order = topological_sort(graph)
    assert order.index("A") < order.index("B") < order.index("C")
