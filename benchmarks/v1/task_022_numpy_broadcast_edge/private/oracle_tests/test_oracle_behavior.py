import pytest
from solution import broadcast_shapes

def test_oracle_happy_path_unit_dimension_broadcasting():
    assert broadcast_shapes((3, 4), (3, 1)) == (3, 4)
    assert broadcast_shapes((3, 1), (3, 4)) == (3, 4)
    assert broadcast_shapes((1, 5), (2, 1)) == (2, 5)

def test_oracle_happy_path_rank_expansion():
    assert broadcast_shapes((5,), (2, 5)) == (2, 5)
    assert broadcast_shapes((2, 5), (5,)) == (2, 5)

def test_oracle_negative_incompatible_dimensions():
    with pytest.raises(ValueError):
        broadcast_shapes((3,), (4,))
    with pytest.raises(ValueError):
        broadcast_shapes((2, 3), (2, 4))

def test_oracle_boundary_identical_shapes():
    assert broadcast_shapes((2, 3, 4), (2, 3, 4)) == (2, 3, 4)
