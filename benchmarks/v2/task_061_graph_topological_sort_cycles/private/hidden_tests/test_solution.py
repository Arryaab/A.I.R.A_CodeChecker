import pytest
from solution import topological_sort, CycleDetectedError

def test_direct_cycle_raises():
    graph = {"A": ["B"], "B": ["A"]}
    with pytest.raises(CycleDetectedError):
        topological_sort(graph)

def test_indirect_cycle_raises():
    graph = {"A": ["B"], "B": ["C"], "C": ["A"], "D": []}
    with pytest.raises(CycleDetectedError):
        topological_sort(graph)
