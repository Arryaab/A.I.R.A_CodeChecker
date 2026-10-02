import pytest
from solution import broadcast_shapes

def test_broadcast_different_ranks():
    assert broadcast_shapes((5, 1, 4), (3, 1)) == (5, 3, 4)

def test_incompatible_shapes_raise():
    with pytest.raises(ValueError):
        broadcast_shapes((3,), (4,))
